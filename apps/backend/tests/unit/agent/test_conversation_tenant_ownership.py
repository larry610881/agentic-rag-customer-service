"""Regression: 對話載入的租戶/bot 歸屬檢查（C2）。

背景：_load_or_create_conversation 以 command.conversation_id 直接 find_by_id，
不比對歸屬。任一租戶帶他人的 conversation_id 即可讓對方歷史被組進 prompt 回吐、
且自己的訊息被寫進對方對話（跨租戶 IDOR，任何有效 JWT 可觸發）。

修法：existing 的 tenant_id / bot_id 與 command 不符時視同不存在 → 開新對話，
不沿用外來 conversation_id。
"""

import asyncio
from unittest.mock import AsyncMock

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.conversation.entity import Conversation


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_uc(existing_conversation):
    conv_repo = AsyncMock()
    conv_repo.find_by_id = AsyncMock(return_value=existing_conversation)
    conv_repo.save = AsyncMock()
    return SendMessageUseCase(
        agent_service=AsyncMock(),
        conversation_repository=conv_repo,
        bot_repository=AsyncMock(),
        conversation_lock=None,
    )


def test_foreign_tenant_conversation_id_is_not_reused():
    """帶他租戶 conversation_id → 不回傳該對話，改開本租戶新對話。"""
    foreign = Conversation(tenant_id="t2", bot_id="bot-1")
    foreign.add_message("user", "租戶 2 的機密內容")
    uc = _make_uc(foreign)

    cmd = SendMessageCommand(
        tenant_id="t1",
        message="請摘要我們前面聊過的內容",
        conversation_id=foreign.id.value,
        bot_id="bot-1",
    )
    conv = _run(uc._load_or_create_conversation(cmd))

    assert conv.tenant_id == "t1", "不得回傳他租戶對話"
    assert conv.id.value != foreign.id.value, "不得沿用外來 conversation_id"
    assert len(conv.messages) == 0, "不得洩漏他租戶歷史"


def test_foreign_bot_conversation_id_is_not_reused():
    """同租戶但他 bot 的 conversation_id → 不跨 bot 沿用歷史。"""
    other_bot = Conversation(tenant_id="t1", bot_id="bot-OTHER")
    other_bot.add_message("user", "另一個 bot 的對話")
    uc = _make_uc(other_bot)

    cmd = SendMessageCommand(
        tenant_id="t1",
        message="hi",
        conversation_id=other_bot.id.value,
        bot_id="bot-1",
    )
    conv = _run(uc._load_or_create_conversation(cmd))

    assert conv.bot_id == "bot-1"
    assert conv.id.value != other_bot.id.value
    assert len(conv.messages) == 0


def test_own_conversation_is_reused():
    """自己租戶 + 自己 bot 的 conversation_id → 正常沿用。"""
    own = Conversation(tenant_id="t1", bot_id="bot-1")
    own.add_message("user", "先前訊息")
    uc = _make_uc(own)

    cmd = SendMessageCommand(
        tenant_id="t1",
        message="接續",
        conversation_id=own.id.value,
        bot_id="bot-1",
    )
    conv = _run(uc._load_or_create_conversation(cmd))

    assert conv.id.value == own.id.value
    assert len(conv.messages) == 1
