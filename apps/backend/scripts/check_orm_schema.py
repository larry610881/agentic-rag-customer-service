"""ORM metadata 與 infra/schema.sql 一致性檢查（#469962）。

本專案沒有 auto-migration：schema.sql 是 DB 的 source of truth，ORM 是程式對 DB 的
假設。兩者 drift 的後果是「整合測試用 create_all 建出的表跟線上不一樣」——測試綠、
線上炸（或反過來）。做法：在暫時 DB 套 schema.sql → SQLAlchemy 反射 → 與
Base.metadata 比對表、欄位、型別、nullable。預設值不比（格式差異太多、雜訊大）。

只能抓 ORM ↔ schema.sql 的 drift；某支 migration 有沒有真的套到某個環境，仍以
各環境的 _applied_migrations 為準。

用法：uv run python scripts/check_orm_schema.py
  連線：CHECK_SCHEMA_PG（預設 postgresql://postgres:postgres@localhost:5432），
  會建立並刪除資料庫 agentic_rag_schema_check。
"""

from __future__ import annotations

import asyncio
import importlib
import os
import pkgutil
import re
import sys
from pathlib import Path

# (表, 欄位) → 理由。只放「已知且刻意保留」的差異；每條要寫清楚何時可以拿掉。
# （eval_datasets.agent_mode 已於 #469965 DROP，項目移除）
ALLOWED: dict[tuple[str, str], str] = {}

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT.parents[1] / "infra" / "schema.sql"
CHECK_DB = "agentic_rag_schema_check"
IGNORED_TABLES = {"_applied_migrations"}  # 只存在 DB 的 migration 紀錄表

Column = tuple[str, bool]  # (正規化型別, nullable)
Tables = dict[str, dict[str, Column]]


def normalize_type(text: str) -> str:
    t = re.sub(r"\s+", " ", text.lower().strip())
    t = t.replace("timestamp with time zone", "timestamptz")
    t = t.replace("character varying", "varchar")
    return {"double precision": "float"}.get(t, t)


def diff_schemas(
    orm: Tables, db: Tables, allowed: dict[tuple[str, str], str]
) -> list[str]:
    """回傳差異描述；allowed 內的 (表, 欄位) 不算差異。"""
    out: list[str] = []
    db = {t: cols for t, cols in db.items() if t not in IGNORED_TABLES}
    for t in sorted(set(orm) - set(db)):
        out.append(f"{t}: 只在 ORM（schema.sql 沒有這張表）")
    for t in sorted(set(db) - set(orm)):
        out.append(f"{t}: 只在 schema.sql（ORM 沒有這張表）")
    for t in sorted(set(orm) & set(db)):
        for c in sorted(set(orm[t]) | set(db[t])):
            if (t, c) in allowed:
                continue
            o, d = orm[t].get(c), db[t].get(c)
            if o is None:
                out.append(f"{t}.{c}: 只在 schema.sql {d}")
            elif d is None:
                out.append(f"{t}.{c}: 只在 ORM {o}")
            elif o[0] != d[0]:
                out.append(f"{t}.{c}: 型別 ORM={o[0]} schema.sql={d[0]}")
            elif o[1] != d[1]:
                out.append(f"{t}.{c}: nullable ORM={o[1]} schema.sql={d[1]}")
    return out


def stale_allowlist(
    orm: Tables, db: Tables, allowed: dict[tuple[str, str], str]
) -> list[str]:
    """允許清單裡已經一致的項目（差異消失了卻沒拿掉 → 清單過期）。"""
    stale = []
    for t, c in sorted(allowed):
        o, d = orm.get(t, {}).get(c), db.get(t, {}).get(c)
        if o == d:
            stale.append(f"{t}.{c}")
    return stale


def orm_tables() -> Tables:
    from sqlalchemy.dialects import postgresql

    import src.infrastructure.db.models as pkg
    from src.infrastructure.db.base import Base

    # models/__init__ 沒匯出全部模組（#65 踩過）：逐一匯入才拿得到完整 metadata
    for m in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg.__name__}.{m.name}")
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    return {
        t.name: {
            c.name: (
                normalize_type(str(c.type.compile(dialect=dialect))),
                bool(c.nullable),
            )
            for c in t.columns
        }
        for t in Base.metadata.sorted_tables
    }


async def schema_sql_tables(base_url: str) -> Tables:
    import asyncpg
    from sqlalchemy import inspect
    from sqlalchemy.ext.asyncio import create_async_engine

    sql = "\n".join(
        line
        for line in SCHEMA_SQL.read_text(encoding="utf-8").splitlines()
        if not line.startswith("\\")  # psql meta-command（\restrict 等）
    )
    admin = await asyncpg.connect(f"{base_url}/postgres")
    try:
        await admin.execute(f"DROP DATABASE IF EXISTS {CHECK_DB}")
        await admin.execute(f"CREATE DATABASE {CHECK_DB}")
    finally:
        await admin.close()
    try:
        conn = await asyncpg.connect(f"{base_url}/{CHECK_DB}")
        try:
            await conn.execute(sql)
        finally:
            await conn.close()
        url = base_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(f"{url}/{CHECK_DB}")
        try:
            async with engine.connect() as c:

                def reflect(sync_conn) -> Tables:  # type: ignore[no-untyped-def]
                    insp = inspect(sync_conn)

                    def typ(t) -> str:  # type: ignore[no-untyped-def]
                        if getattr(t, "timezone", False):
                            return "timestamptz"
                        return normalize_type(str(t))

                    return {
                        t: {
                            col["name"]: (typ(col["type"]), bool(col["nullable"]))
                            for col in insp.get_columns(t)
                        }
                        for t in insp.get_table_names()
                    }

                return await c.run_sync(reflect)
        finally:
            await engine.dispose()
    finally:
        admin = await asyncpg.connect(f"{base_url}/postgres")
        try:
            await admin.execute(f"DROP DATABASE IF EXISTS {CHECK_DB}")
        finally:
            await admin.close()


def main() -> int:
    base_url = os.getenv(
        "CHECK_SCHEMA_PG", "postgresql://postgres:postgres@localhost:5432"
    ).rstrip("/")
    orm = orm_tables()
    db = asyncio.run(schema_sql_tables(base_url))
    diffs = diff_schemas(orm, db, ALLOWED)
    stale = stale_allowlist(orm, db, ALLOWED)
    print(f"ORM {len(orm)} 張表、schema.sql {len(db)} 張表；允許清單 {len(ALLOWED)} 條")
    for (t, c), why in sorted(ALLOWED.items()):
        print(f"  允許 {t}.{c}：{why}")
    for s in stale:
        print(
            "##vso[task.logissue type=error]"
            f"允許清單過期：{s} 已一致，請從 ALLOWED 拿掉"
        )
    for d in diffs:
        print(f"##vso[task.logissue type=error]ORM 與 schema.sql 不一致：{d}")
    if diffs or stale:
        print(
            f"{len(diffs)} 筆差異、{len(stale)} 條過期允許。修法：以線上 DB 為準改 ORM "
            "或 schema.sql（需要改 DB 就走 migration 五步流程）；"
            "刻意保留的差異加進 ALLOWED 並寫理由。"
        )
        return 1
    print("ORM 與 schema.sql 一致")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
