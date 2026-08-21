"""Regression: gate 啟用時 rollback 應免重驗直接發布（H1）。

回朔複製歷史已發布快照建新版本後呼叫 publish(verdict=SKIPPED)。原本 publish 在
gate 啟用時無條件以 _resolve_gate_verdict 覆寫 verdict，對 source=rollback 的 draft
一律 raise GateBlockedError → 閘門開啟的環境（最需要緊急回朔者）rollback 全不可用。
"""

import asyncio
from unittest.mock import AsyncMock

from src.application.prompt_gate.version_use_cases import (
    PublishConfigVersionUseCase,
    RollbackConfigVersionCommand,
    RollbackConfigVersionUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId
from src.domain.prompt_gate.config_snapshot import take_snapshot
from src.domain.prompt_gate.entity import (
    SOURCE_SEED,
    STATUS_PUBLISHED,
    VERDICT_SKIPPED,
    BotConfigVersion,
)

TENANT = "t-gate"
BOT_ID = "bot-gate"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make(store, bot, *, gate_enabled: bool):
    version_repo = AsyncMock()

    async def _save(v):
        store[v.id] = v

    async def _find_by_id(vid, tenant_id):
        v = store.get(vid)
        return v if v and v.tenant_id == tenant_id else None

    async def _next_no(bot_id):
        return max((v.version_no for v in store.values()), default=0) + 1

    async def _set_current(bot_id, vid):
        for v in store.values():
            if v.bot_id == bot_id:
                v.is_current = v.id == vid

    version_repo.save.side_effect = _save
    version_repo.find_by_id.side_effect = _find_by_id
    version_repo.next_version_no.side_effect = _next_no
    version_repo.set_current.side_effect = _set_current

    bot_repo = AsyncMock()
    bot_repo.find_by_id = AsyncMock(return_value=bot)
    bot_repo.save = AsyncMock()

    tenant_repo = AsyncMock()
    tenant = type("T", (), {"prompt_gate_enabled": gate_enabled})()
    tenant_repo.find_by_id = AsyncMock(return_value=tenant)

    publish = PublishConfigVersionUseCase(
        bot_repo, version_repo, tenant_repository=tenant_repo
    )
    rollback = RollbackConfigVersionUseCase(bot_repo, version_repo, publish)
    return rollback


def test_rollback_succeeds_when_gate_block_enabled():
    """gate_mode=block + prompt_gate_enabled=True 下 rollback 應成功發布。"""
    bot = Bot(id=BotId(value=BOT_ID), tenant_id=TENANT, name="b",
              base_prompt="舊版", gate_mode="block")
    store: dict = {}
    # 歷史已發布版本 v1（回朔目標），快照為「舊版」
    v1 = BotConfigVersion(
        tenant_id=TENANT, bot_id=BOT_ID, version_no=1,
        config_snapshot=take_snapshot(bot), status=STATUS_PUBLISHED,
        is_current=False, source=SOURCE_SEED, gate_verdict=VERDICT_SKIPPED,
    )
    store[v1.id] = v1
    # 目前 bot 設定已改成「新版」，rollback 回 v1 有差異
    bot.base_prompt = "新版"

    rollback = _make(store, bot, gate_enabled=True)
    result = _run(rollback.execute(RollbackConfigVersionCommand(
        tenant_id=TENANT, bot_id=BOT_ID, target_version_id=v1.id,
    )))
    assert result.status == STATUS_PUBLISHED
    assert result.is_current is True
    assert bot.base_prompt == "舊版"  # 已套回 v1 快照
