"""Regression: 版本狀態轉移的樂觀鎖（M3/M6）。

save_status_transition 以 `WHERE status=expected_status` 做條件式 UPDATE。並發
publish/reject、或連點兩下驗證時只有一方 rowcount=1；輸的一方讀到的 expected_status
已被搶先改掉 → rowcount=0 → 拋 InvalidVersionTransitionError（interfaces 層 409），
而非無條件覆寫寫出 entity 明文禁止的轉移（published→rejected）或建立第二個背景 run。
"""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.prompt_gate.entity import (
    STATUS_DRAFT,
    STATUS_VALIDATING,
    BotConfigVersion,
    InvalidVersionTransitionError,
)
from src.infrastructure.db.models.bot_config_version_model import (
    BotConfigVersionModel,
)
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.repositories.bot_config_version_repository import (
    SQLAlchemyBotConfigVersionRepository,
)


async def _seed_draft(session: AsyncSession) -> BotConfigVersion:
    session.add(TenantModel(id="t-lock", name="lock-tenant"))
    await session.flush()
    session.add(
        BotModel(
            id="b-lock", short_code="blk001", tenant_id="t-lock",
            name="lock-bot",
        )
    )
    await session.flush()
    model = BotConfigVersionModel(
        id="ver-lock-1",
        tenant_id="t-lock",
        bot_id="b-lock",
        version_no=1,
        config_snapshot={"base_prompt": "x"},
        snapshot_schema=1,
        changed_fields=["base_prompt"],
        status=STATUS_DRAFT,
        is_current=False,
        source="manual",
    )
    session.add(model)
    await session.commit()
    return BotConfigVersion(
        id="ver-lock-1", tenant_id="t-lock", bot_id="b-lock",
        version_no=1, status=STATUS_DRAFT,
    )


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_second_transition_from_stale_status_raises(test_engine):
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _scenario():
        async with factory() as session:
            version = await _seed_draft(session)
            repo = SQLAlchemyBotConfigVersionRepository(session)

            # 第一方：draft→validating 成功
            version.status = STATUS_VALIDATING
            await repo.save_status_transition(
                version, expected_status=STATUS_DRAFT, action="validate"
            )

            # 第二方仍以為是 draft（stale read）→ rowcount=0 → 409
            loser = BotConfigVersion(
                id="ver-lock-1", tenant_id="t-lock", bot_id="b-lock",
                version_no=1, status=STATUS_VALIDATING,
            )
            with pytest.raises(InvalidVersionTransitionError):
                await repo.save_status_transition(
                    loser, expected_status=STATUS_DRAFT, action="validate"
                )

    _run(_scenario())
