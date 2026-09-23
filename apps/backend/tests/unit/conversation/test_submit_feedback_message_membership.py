"""Regression：回饋的 message 必須屬於該 conversation（Issue #101 B8）。

舊碼只驗 conversation 屬於呼叫者，message_id 可以是任何訊息：租戶 A 能在
租戶 B 的訊息上先建立回饋（message_id 唯一），B 自己的使用者之後就回饋不了；
也能把回饋掛到自己其他對話的訊息上，汙染報表。與跨租戶同一個 404，不透露訊息存在。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackCommand,
    SubmitFeedbackUseCase,
)
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.domain.shared.exceptions import EntityNotFoundError


def _conversation_with(message_ids: list[str]) -> Conversation:
    return Conversation(
        id=ConversationId(value="conv-a"),
        tenant_id="tenant-a",
        messages=[
            Message(
                id=MessageId(value=mid),
                conversation_id="conv-a",
                role="assistant",
                content="答",
            )
            for mid in message_ids
        ],
    )


def _use_case(conversation: Conversation) -> tuple[SubmitFeedbackUseCase, AsyncMock]:
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = conversation
    fb_repo = AsyncMock()
    fb_repo.find_by_message_id.return_value = None
    return SubmitFeedbackUseCase(fb_repo, conv_repo), fb_repo


def _cmd(message_id: str) -> SubmitFeedbackCommand:
    return SubmitFeedbackCommand(
        tenant_id="tenant-a",
        conversation_id="conv-a",
        message_id=message_id,
        channel="web",
        rating="thumbs_up",
    )


def test_不屬於該對話的訊息不能建立回饋():
    uc, fb_repo = _use_case(_conversation_with(["msg-own"]))
    with pytest.raises(EntityNotFoundError):
        asyncio.run(uc.execute(_cmd("msg-of-tenant-b")))
    fb_repo.save.assert_not_awaited()


def test_屬於該對話的訊息照常建立回饋():
    uc, fb_repo = _use_case(_conversation_with(["msg-own"]))
    feedback = asyncio.run(uc.execute(_cmd("msg-own")))
    assert feedback.message_id == "msg-own"
    fb_repo.save.assert_awaited_once()
