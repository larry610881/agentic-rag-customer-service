"""Regression: 孤兒清理的多實例寬限窗（M7）。

滾動部署／autoscale 期間新舊實例並存。新實例啟動時的孤兒清理若無條件把所有
queued/running run 標 error，會殺掉舊實例上剛啟動、仍健康執行中的 run（token 白燒
＋兩實例狀態互踩）。mark_orphans_error 加 created_at 寬限窗：只清超過 grace_minutes
的 run；剛啟動者視為其他實例仍在跑，不動。
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infrastructure.db.models.bot_config_version_model import (
    BotConfigVersionModel,
)
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.prompt_gate_run_model import (
    PromptGateRunModel,
)
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.repositories.prompt_gate_run_repository import (
    SQLAlchemyPromptGateRunRepository,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _seed_run(session, run_id, version_id, created_at):
    session.add(
        PromptGateRunModel(
            id=run_id, tenant_id="t-m7", bot_id="b-m7",
            version_id=version_id, status="running", dataset_ids=[],
            repeats=1, soft_threshold=0.8, created_at=created_at,
        )
    )


def test_recent_run_spared_old_run_cleaned(test_engine):
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _scenario():
        now = datetime.now(timezone.utc)
        async with factory() as session:
            session.add(TenantModel(id="t-m7", name="m7-tenant"))
            await session.flush()
            session.add(
                BotModel(
                    id="b-m7", short_code="m7b001", tenant_id="t-m7",
                    name="m7-bot",
                )
            )
            await session.flush()
            for vid in ("v-recent", "v-old"):
                session.add(
                    BotConfigVersionModel(
                        id=vid, tenant_id="t-m7", bot_id="b-m7",
                        version_no=1 if vid == "v-recent" else 2,
                        config_snapshot={}, snapshot_schema=1,
                        changed_fields=[], status="validating",
                        is_current=False, source="manual",
                    )
                )
            await session.flush()
            # 其他實例剛啟動（2 分鐘前）＝健康
            await _seed_run(
                session, "run-recent", "v-recent",
                now - timedelta(minutes=2),
            )
            # 真正的孤兒（90 分鐘前，遠超任何真實 gate run）
            await _seed_run(
                session, "run-old", "v-old", now - timedelta(minutes=90),
            )
            await session.commit()

            repo = SQLAlchemyPromptGateRunRepository(session)
            reverted_version_ids = await repo.mark_orphans_error()

            # 只有老孤兒被清；剛啟動的健康 run 不動
            assert reverted_version_ids == ["v-old"]

            recent = await session.get(PromptGateRunModel, "run-recent")
            old = await session.get(PromptGateRunModel, "run-old")
            assert recent.status == "running"  # 未被殺
            assert old.status == "error"

    _run(_scenario())
