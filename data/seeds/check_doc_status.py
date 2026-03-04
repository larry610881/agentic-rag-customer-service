"""檢查 documents 和 processing_tasks 的狀態分布。

Usage:
  cd apps/backend && DATABASE_URL_OVERRIDE="postgresql+asyncpg://..." \
    uv run python ../../data/seeds/check_doc_status.py
"""

import asyncio
import sys
from pathlib import Path

backend_src = Path(__file__).resolve().parent.parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_src))

from src.config import Settings  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy import text  # noqa: E402


async def check() -> None:
    settings = Settings()
    engine = create_async_engine(
        settings.database_url, echo=False, connect_args={"timeout": 30}
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        r = await session.execute(text(
            "SELECT status, COUNT(*) as cnt FROM documents GROUP BY status ORDER BY status"
        ))
        print("=== Document Status ===")
        for row in r.all():
            print(f"  {row.status}: {row.cnt}")

        r = await session.execute(text(
            "SELECT status, COUNT(*) as cnt FROM processing_tasks GROUP BY status ORDER BY status"
        ))
        print("\n=== Task Status ===")
        for row in r.all():
            print(f"  {row.status}: {row.cnt}")

        r = await session.execute(text(
            "SELECT id, filename, status FROM documents WHERE status IN ('pending', 'processing', 'failed') ORDER BY created_at"
        ))
        rows = r.all()
        if rows:
            print(f"\n=== 未完成的文件 ({len(rows)}) ===")
            for row in rows:
                print(f"  [{row.status}] {row.filename} ({row.id})")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check())
