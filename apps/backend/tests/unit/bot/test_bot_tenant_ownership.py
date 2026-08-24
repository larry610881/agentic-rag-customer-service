"""Regression: bot Get/Update/Delete 的租戶歸屬檢查（C8/C9）。

背景：GET/PUT/DELETE /api/v1/bots/{id} 的 use case 以純 bot_id find_by_id、不比對
tenant。任一租戶持合法 JWT 即可讀取（C8，含明文 LINE 憑證）、竄改或刪除（C9）他人
bot。修法：use case 收 tenant_id + role，bot.tenant_id 不符且非 system_admin →
raise EntityNotFoundError（404，不洩漏存在性）。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.application.bot.delete_bot_use_case import DeleteBotUseCase
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.shared.exceptions import EntityNotFoundError


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _bot(tenant_id="owner"):
    return Bot(
        id=BotId(value="bot-1"),
        short_code=BotShortCode(value="sc1"),
        tenant_id=tenant_id,
        name="Owner Bot",
    )


def _bot_repo(bot):
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=bot)
    repo.delete = AsyncMock()
    repo.save = AsyncMock()
    return repo


# --- GET (C8) ---

def test_get_bot_foreign_tenant_raises_not_found():
    uc = GetBotUseCase(_bot_repo(_bot("owner")))
    with pytest.raises(EntityNotFoundError):
        _run(uc.execute("bot-1", tenant_id="attacker"))


def test_get_bot_own_tenant_ok():
    uc = GetBotUseCase(_bot_repo(_bot("owner")))
    bot = _run(uc.execute("bot-1", tenant_id="owner"))
    assert bot.id.value == "bot-1"


def test_get_bot_system_admin_bypass():
    uc = GetBotUseCase(_bot_repo(_bot("owner")))
    bot = _run(uc.execute("bot-1", tenant_id="", role="system_admin"))
    assert bot.id.value == "bot-1"


# --- DELETE (C9) ---

def test_delete_bot_foreign_tenant_raises_and_no_delete():
    repo = _bot_repo(_bot("owner"))
    uc = DeleteBotUseCase(repo)
    with pytest.raises(EntityNotFoundError):
        _run(uc.execute("bot-1", tenant_id="attacker"))
    repo.delete.assert_not_called()


def test_delete_bot_own_tenant_ok():
    repo = _bot_repo(_bot("owner"))
    uc = DeleteBotUseCase(repo)
    _run(uc.execute("bot-1", tenant_id="owner"))
    repo.delete.assert_called_once()


# --- UPDATE (C9) ---

def test_update_bot_foreign_tenant_raises_and_no_save():
    repo = _bot_repo(_bot("owner"))
    uc = UpdateBotUseCase(repo)
    cmd = UpdateBotCommand(bot_id="bot-1", tenant_id="attacker", name="hijacked")
    with pytest.raises(EntityNotFoundError):
        _run(uc.execute(cmd))
    repo.save.assert_not_called()
