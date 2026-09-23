"""Regression：widget 匿名訪客的回饋路徑同樣受租戶與訊息歸屬檢查（Issue #101）。

widget 端點以 bot 的租戶呼叫同一個 SubmitFeedbackUseCase；匿名訪客不能拿別家
租戶的 conversation / message 改寫或佔用回饋。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import Response

from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackUseCase,
)
from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.value_objects import BotId
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api import widget_router as w


def _principal(
    visitor_id: str = "v-1", end_user_id: str | None = None
) -> w.WidgetPrincipal:
    bot = Bot(
        id=BotId(value="bot-a"),
        tenant_id="tenant-a",
        name="A 的 widget",
        knowledge_base_ids=[],
        llm_params=BotLLMParams(),
    )
    return w.WidgetPrincipal(
        bot=bot, origin="", visitor_id=visitor_id, end_user_id=end_user_id
    )


def _conversation(
    tenant_id: str,
    message_ids: list[str],
    bot_id: str = "bot-a",
    visitor_id: str | None = "v-1",
) -> Conversation:
    return Conversation(
        id=ConversationId(value="conv-x"),
        tenant_id=tenant_id,
        bot_id=bot_id,
        visitor_id=visitor_id,
        messages=[
            Message(
                id=MessageId(value=m),
                conversation_id="conv-x",
                role="assistant",
                content="答",
            )
            for m in message_ids
        ],
    )


def _call(
    conversation: Conversation,
    message_id: str,
    principal: w.WidgetPrincipal | None = None,
) -> tuple[dict, AsyncMock]:
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = conversation
    fb_repo = AsyncMock()
    fb_repo.find_by_message_id.return_value = None
    result = asyncio.run(
        w.widget_feedback(
            short_code="sc",
            body=w.WidgetFeedbackRequest(
                conversation_id="conv-x", message_id=message_id, rating="thumbs_down"
            ),
            response=Response(),
            principal=principal or _principal(),
            use_case=SubmitFeedbackUseCase(fb_repo, conv_repo),
        )
    )
    return result, fb_repo


def test_widget_訪客不能對別家租戶的對話回饋():
    with pytest.raises(EntityNotFoundError):
        _call(_conversation("tenant-b", ["msg-b"]), "msg-b")


def test_widget_訪客不能對不屬於該對話的訊息回饋():
    with pytest.raises(EntityNotFoundError):
        _call(_conversation("tenant-a", ["msg-a"]), "msg-of-tenant-b")


def test_widget_訪客對自家對話的訊息可正常回饋():
    result, fb_repo = _call(_conversation("tenant-a", ["msg-a"]), "msg-a")
    assert result == {"success": True}
    fb_repo.save.assert_awaited_once()


# ---- #102：同租戶內也不能跨 bot、跨訪客 ----


def test_widget_訪客不能對同租戶其他訪客的對話回饋():
    with pytest.raises(EntityNotFoundError):
        _call(_conversation("tenant-a", ["msg-a"], visitor_id="v-other"), "msg-a")


def test_widget_訪客不能對同租戶其他_bot_的對話回饋():
    with pytest.raises(EntityNotFoundError):
        _call(_conversation("tenant-a", ["msg-a"], bot_id="bot-other"), "msg-a")


def test_沒有訪客綁定的對話不接受_widget_回饋():
    with pytest.raises(EntityNotFoundError):
        _call(_conversation("tenant-a", ["msg-a"], visitor_id=None), "msg-a")


def test_identify_後仍可對識別前的對話回饋():
    """identify() 前的對話記的是匿名 visitor_id，之後票帶 end_user_id；兩者都算本人。"""
    principal = _principal(visitor_id="v-1", end_user_id="host-user-9")
    result, _ = _call(_conversation("tenant-a", ["msg-a"]), "msg-a", principal)
    assert result == {"success": True}


def test_identify_後的對話以宿主使用者_id_比對():
    principal = _principal(visitor_id="v-1", end_user_id="host-user-9")
    conv = _conversation("tenant-a", ["msg-a"], visitor_id="host-user-9")
    result, _ = _call(conv, "msg-a", principal)
    assert result == {"success": True}

