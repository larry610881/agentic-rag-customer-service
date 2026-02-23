"""對話歷史查詢 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.get_conversation_use_case import (
    GetConversationUseCase,
)
from src.application.conversation.list_conversations_use_case import (
    ListConversationsUseCase,
)
from src.domain.conversation.entity import Conversation
from src.domain.conversation.value_objects import ConversationId

scenarios("unit/conversation/conversation_history.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given(parsers.parse('租戶 "{tenant_id}" 有 {count:d} 個對話'))
def tenant_has_conversations(context, tenant_id, count):
    conversations = [
        Conversation(
            id=ConversationId(value=f"conv-{i}"),
            tenant_id=tenant_id,
        )
        for i in range(count)
    ]
    mock_repo = AsyncMock()
    mock_repo.find_by_tenant = AsyncMock(return_value=conversations)
    context["list_use_case"] = ListConversationsUseCase(
        conversation_repository=mock_repo,
    )
    context["tenant_id"] = tenant_id


@when(parsers.parse('查詢租戶 "{tenant_id}" 的對話列表'))
def query_conversation_list(context, tenant_id):
    context["result"] = _run(
        context["list_use_case"].execute(tenant_id=tenant_id)
    )


@then(parsers.parse("應回傳 {count:d} 個對話"))
def verify_conversation_count(context, count):
    assert len(context["result"]) == count


@given(parsers.parse("一個已存在的對話含 {count:d} 條訊息"))
def conversation_with_messages(context, count):
    conv = Conversation(
        id=ConversationId(value="conv-detail"),
        tenant_id="tenant-001",
    )
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        conv.add_message(role, f"訊息 {i + 1}")

    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=conv)
    context["get_use_case"] = GetConversationUseCase(
        conversation_repository=mock_repo,
    )
    context["conv_id"] = "conv-detail"
    context["expected_count"] = count


@when("查詢該對話的詳情")
def query_conversation_detail(context):
    context["result"] = _run(
        context["get_use_case"].execute(conversation_id=context["conv_id"])
    )


@then(parsers.parse("應回傳該對話含 {count:d} 條訊息"))
def verify_message_count(context, count):
    assert context["result"] is not None
    assert len(context["result"].messages) == count
