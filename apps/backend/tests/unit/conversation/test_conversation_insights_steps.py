"""Conversation Insights Use Cases — BDD Step Definitions (Unit)"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.get_conversation_messages_use_case import (
    GetConversationMessagesQuery,
    GetConversationMessagesUseCase,
)
from src.application.conversation.get_conversation_token_usage_use_case import (
    GetConversationTokenUsageQuery,
    GetConversationTokenUsageUseCase,
)
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/conversation/conversation_insights.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


# ---- Given ----


def _make_conversation(conv_id: str, tenant_id: str, msg_count: int = 3) -> Conversation:
    msgs = [
        Message(
            id=MessageId(value=f"msg-{i}"),
            conversation_id=conv_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"訊息內容 {i}",
            created_at=datetime(2026, 4, 23, 10, i, 0, tzinfo=timezone.utc),
        )
        for i in range(msg_count)
    ]
    return Conversation(
        id=ConversationId(value=conv_id),
        tenant_id=tenant_id,
        bot_id="bot-001",
        messages=msgs,
        created_at=datetime(2026, 4, 23, 10, 0, 0, tzinfo=timezone.utc),
        summary="conversation summary",
        message_count=msg_count,
    )


@given(parsers.parse('一個 conversation "{conv_id}" 帶 3 筆 messages'))
def setup_conv_with_msgs(ctx, conv_id):
    conv = _make_conversation(conv_id, tenant_id="tenant-A", msg_count=3)
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=conv)
    ctx["repo"] = repo
    ctx["use_case"] = GetConversationMessagesUseCase(conversation_repo=repo)
    ctx["conv_id"] = conv_id


@given(parsers.parse('一個屬於租戶 "{tenant_id}" 的 conversation "{conv_id}"'))
def setup_cross_tenant_conv(ctx, conv_id, tenant_id):
    conv = _make_conversation(conv_id, tenant_id=tenant_id, msg_count=2)
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=conv)
    ctx["repo"] = repo
    ctx["use_case"] = GetConversationMessagesUseCase(conversation_repo=repo)
    ctx["conv_id"] = conv_id
    ctx["conv_tenant"] = tenant_id


@given(
    parsers.parse(
        'conversation "{conv_id}" 有 4 筆 usage (2 種 request_type)'
    )
)
def setup_conv_with_usage(ctx, conv_id):
    # Mock conversation
    conv = _make_conversation(conv_id, tenant_id="tenant-A", msg_count=2)
    conv_repo = AsyncMock()
    conv_repo.find_by_id = AsyncMock(return_value=conv)

    # Mock session + SQL result：回 2 筆 grouped rows（按 request_type 聚合後）
    row_chat = MagicMock()
    row_chat.model = "gpt-5.1"
    row_chat.request_type = "chat_web"
    row_chat.kb_id = None
    row_chat.kb_name = None
    row_chat.bot_id = "bot-001"
    row_chat.input_tokens = 100
    row_chat.output_tokens = 50
    row_chat.cache_read_tokens = 0
    row_chat.cache_creation_tokens = 0
    row_chat.estimated_cost = 0.01
    row_chat.message_count = 2

    row_ocr = MagicMock()
    row_ocr.model = "claude-haiku-4-5"
    row_ocr.request_type = "ocr"
    row_ocr.kb_id = "kb-A"
    row_ocr.kb_name = "KB A"
    row_ocr.bot_id = None
    row_ocr.input_tokens = 200
    row_ocr.output_tokens = 100
    row_ocr.cache_read_tokens = 50
    row_ocr.cache_creation_tokens = 10
    row_ocr.estimated_cost = 0.02
    row_ocr.message_count = 2

    mock_result = MagicMock()
    mock_result.all = MagicMock(return_value=[row_chat, row_ocr])

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.close = AsyncMock()

    def session_factory():
        return mock_session

    ctx["conv_repo"] = conv_repo
    ctx["session_factory"] = session_factory
    ctx["use_case"] = GetConversationTokenUsageUseCase(
        conversation_repo=conv_repo,
        session_factory=session_factory,
    )
    ctx["conv_id"] = conv_id


@given(parsers.parse('conversation "{conv_id}" 無任何 usage'))
def setup_empty_conv(ctx, conv_id):
    conv = _make_conversation(conv_id, tenant_id="tenant-A", msg_count=0)
    conv_repo = AsyncMock()
    conv_repo.find_by_id = AsyncMock(return_value=conv)

    mock_result = MagicMock()
    mock_result.all = MagicMock(return_value=[])
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.close = AsyncMock()

    ctx["use_case"] = GetConversationTokenUsageUseCase(
        conversation_repo=conv_repo,
        session_factory=lambda: mock_session,
    )
    ctx["conv_id"] = conv_id


# ---- When ----


@when(
    parsers.parse("system_admin 呼叫 GetConversationMessagesUseCase"),
    target_fixture="result",
)
def call_get_messages_system_admin(ctx):
    return _run(
        ctx["use_case"].execute(
            GetConversationMessagesQuery(
                conversation_id=ctx["conv_id"],
                role="system_admin",
                tenant_id="",
            )
        )
    )


@when(parsers.parse('tenant_admin 以 "{tenant_id}" 身份呼叫'))
def call_cross_tenant(ctx, tenant_id):
    try:
        _run(
            ctx["use_case"].execute(
                GetConversationMessagesQuery(
                    conversation_id=ctx["conv_id"],
                    role="tenant_admin",
                    tenant_id=tenant_id,
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


@when("system_admin 呼叫", target_fixture="result")
def call_system_admin(ctx):
    return _run(
        ctx["use_case"].execute(
            GetConversationMessagesQuery(
                conversation_id=ctx["conv_id"],
                role="system_admin",
                tenant_id="",
            )
        )
    )


@when(parsers.parse('system_admin 查不存在的 conversation "{cid}"'))
def call_not_found(ctx, cid):
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    use_case = GetConversationMessagesUseCase(conversation_repo=repo)
    try:
        _run(
            use_case.execute(
                GetConversationMessagesQuery(
                    conversation_id=cid, role="system_admin", tenant_id=""
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


@when(
    "system_admin 呼叫 GetConversationTokenUsageUseCase",
    target_fixture="result",
)
def call_token_usage(ctx):
    return _run(
        ctx["use_case"].execute(
            GetConversationTokenUsageQuery(
                conversation_id=ctx["conv_id"],
                role="system_admin",
                tenant_id="",
            )
        )
    )


# ---- Then ----


@then("結果應包含 3 筆 messages 與 conversation metadata")
def verify_3_messages(result):
    assert len(result.messages) == 3
    assert result.summary == "conversation summary"
    assert result.bot_id == "bot-001"


@then("應拋出 EntityNotFoundError")
def verify_not_found(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)


@then("結果應回傳該 conversation")
def verify_cross_tenant_ok(result):
    assert result is not None
    assert len(result.messages) == 2


@then("by_request_type 應有 2 筆聚合結果")
def verify_2_grouped(result):
    assert len(result.by_request_type) == 2


@then("totals.estimated_cost 應等於 4 筆加總")
def verify_cost_sum(result):
    # row_chat: 0.01 + row_ocr: 0.02 = 0.03
    assert abs(result.totals.estimated_cost - 0.03) < 1e-9


@then("totals.message_count 應為 0")
def verify_empty_msg_count(result):
    assert result.totals.message_count == 0


@then("by_request_type 應為空陣列")
def verify_empty_by_type(result):
    assert result.by_request_type == []
