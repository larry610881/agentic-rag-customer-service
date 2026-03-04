"""批次重置卡住的文件並逐一 reprocess。

將所有 pending/processing/failed 的文件重置為 pending，
然後逐一觸發 reprocess（避免連線池爆掉）。

Usage:
  cd apps/backend && DATABASE_URL_OVERRIDE="postgresql+asyncpg://..." \
    uv run python ../../data/seeds/batch_reprocess.py
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


async def main() -> None:
    settings = Settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"timeout": 30},
        pool_size=2,
        max_overflow=0,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1. 查詢所有未完成文件
    async with async_session() as session:
        r = await session.execute(text(
            "SELECT id, filename, status FROM documents "
            "WHERE status IN ('pending', 'processing', 'failed') "
            "ORDER BY created_at"
        ))
        stuck_docs = r.all()

    if not stuck_docs:
        print("沒有卡住的文件")
        await engine.dispose()
        return

    print(f"找到 {len(stuck_docs)} 個未完成文件")

    # 2. 全部重置為 pending
    async with async_session() as session:
        async with session.begin():
            await session.execute(text(
                "UPDATE documents SET status = 'pending' "
                "WHERE status IN ('processing', 'failed')"
            ))
            await session.execute(text(
                "UPDATE processing_tasks SET status = 'pending', error_message = '' "
                "WHERE status IN ('processing', 'failed')"
            ))
    print("已重置所有卡住的文件和任務為 pending")

    # 3. 逐一觸發 reprocess（透過 API）
    print("\n接下來請透過前端或 API 逐一 reprocess：")
    for doc in stuck_docs:
        print(f"  curl -X POST $API_URL/api/v1/knowledge-bases/KB_ID/documents/{doc.id}/reprocess -H 'Authorization: Bearer TOKEN'")

    print(f"\n或者在前端「知識庫 → 文件列表」中點擊每個文件的「重新處理」按鈕")
    print("建議一次只處理 2-3 個，等完成後再處理下一批")

    await engine.dispose()
    print("\n=== 重置完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
