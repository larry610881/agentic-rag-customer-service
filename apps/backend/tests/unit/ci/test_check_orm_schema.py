"""ORM ↔ schema.sql 比對邏輯（#469962）。比對本身在 CI 整合 job 對真實 Postgres 跑。"""

from scripts.check_orm_schema import (
    IGNORED_TABLES,
    diff_schemas,
    normalize_type,
    stale_allowlist,
)

ORM = {"bots": {"id": ("varchar(36)", False), "cases": ("jsonb", False)}}


def test_一致時無差異():
    assert diff_schemas(ORM, {"bots": dict(ORM["bots"])}, {}) == []


def test_型別_nullable_欄位與表的差異都抓得到():
    db = {
        "bots": {
            "id": ("varchar(36)", True),
            "cases": ("json", False),
            "old": ("text", True),
        },
        "extra": {"id": ("text", False)},
    }
    diffs = diff_schemas({**ORM, "orm_only": {"id": ("text", False)}}, db, {})
    assert diffs == [
        "orm_only: 只在 ORM（schema.sql 沒有這張表）",
        "extra: 只在 schema.sql（ORM 沒有這張表）",
        "bots.cases: 型別 ORM=jsonb schema.sql=json",
        "bots.id: nullable ORM=False schema.sql=True",
        "bots.old: 只在 schema.sql ('text', True)",
    ]


def test_允許清單內的差異不算_一致後視為過期():
    db = {"bots": {**ORM["bots"], "old": ("text", True)}}
    allowed = {("bots", "old"): "待 DROP"}
    assert diff_schemas(ORM, db, allowed) == []
    assert stale_allowlist(ORM, db, allowed) == []
    assert stale_allowlist(ORM, {"bots": dict(ORM["bots"])}, allowed) == ["bots.old"]


def test_migration_紀錄表不列入比對():
    db = {
        "bots": dict(ORM["bots"]),
        **{t: {"x": ("text", False)} for t in IGNORED_TABLES},
    }
    assert diff_schemas(ORM, db, {}) == []


def test_型別正規化():
    assert normalize_type("TIMESTAMP WITH TIME ZONE") == "timestamptz"
    assert normalize_type("CHARACTER VARYING(20)") == "varchar(20)"
    assert normalize_type("DOUBLE PRECISION") == "float"
