"""對話紀錄依 bot_id 隔離 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.conversation.list_conversations_use_case import (
    ListConversationsUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.conversation.entity import Conversation
from src.domain.shared.exceptions import DomainException

scenarios("unit/conversation/conversation_bot_filter.feature")


def _run(coro):
    """同步包裝 async 呼叫（pytest-bdd v8 step 必須是 def，不可 async def）"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


# ── Scenario 1 & 2: 建立對話時儲存 bot_id ──


@given(parsers.parse('一個屬於 tenant "{tenant_id}" 且 bot 為 "{bot_id}" 的新對話'))
def conversation_with_bot(context, tenant_id, bot_id):
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=None)
    mock_repo.save = AsyncMock()

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="ok", tool_calls=[], sources=[])
    )

    context["mock_repo"] = mock_repo
    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_repo,
    )
    context["command"] = SendMessageCommand(
        tenant_id=tenant_id, bot_id=bot_id, message="hi"
    )


@given(parsers.parse('一個屬於 tenant "{tenant_id}" 且未指定 bot 的新對話'))
def conversation_without_bot(context, tenant_id):
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=None)
    mock_repo.save = AsyncMock()

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="ok", tool_calls=[], sources=[])
    )

    context["mock_repo"] = mock_repo
    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_repo,
    )
    context["command"] = SendMessageCommand(
        tenant_id=tenant_id, message="hi"
    )


@when("透過 Use Case 儲存該對話")
def execute_send_message(context):
    _run(context["use_case"].execute(context["command"]))


@then(parsers.parse('Repository 應收到 bot_id 為 "{expected_bot_id}" 的對話'))
def verify_bot_id_saved(context, expected_bot_id):
    saved_conversation = context["mock_repo"].save.call_args[0][0]
    assert saved_conversation.bot_id == expected_bot_id


@then("Repository 應收到 bot_id 為空的對話")
def verify_bot_id_none(context):
    saved_conversation = context["mock_repo"].save.call_args[0][0]
    assert saved_conversation.bot_id is None


# ── Scenario 3 & 4: 依 bot_id 過濾對話列表 ──


@given(
    parsers.parse(
        '租戶 "{tenant_id}" 有 {total:d} 筆對話，其中 {bot_count:d} 筆屬於 bot "{bot_id}"'
    )
)
def setup_conversations_with_bot(context, tenant_id, total, bot_count, bot_id):
    all_conversations = [
        Conversation(tenant_id=tenant_id, bot_id=bot_id)
        for _ in range(bot_count)
    ] + [
        Conversation(tenant_id=tenant_id, bot_id="bot-other")
        for _ in range(total - bot_count)
    ]

    filtered_conversations = [
        c for c in all_conversations if c.bot_id == bot_id
    ]

    mock_repo = AsyncMock()

    async def mock_find_by_tenant(tid, *, bot_id=None):
        if bot_id is not None:
            return [c for c in all_conversations if c.bot_id == bot_id]
        return all_conversations

    mock_repo.find_by_tenant = AsyncMock(side_effect=mock_find_by_tenant)

    context["mock_repo"] = mock_repo
    context["tenant_id"] = tenant_id
    context["bot_id"] = bot_id
    context["use_case"] = ListConversationsUseCase(
        conversation_repository=mock_repo
    )


@when(parsers.parse('以 bot_id "{bot_id}" 查詢對話列表'), target_fixture="result")
def query_with_bot_id(context, bot_id):
    return _run(
        context["use_case"].execute(context["tenant_id"], bot_id=bot_id)
    )


@when("不帶 bot_id 查詢對話列表", target_fixture="result")
def query_without_bot_id(context):
    return _run(context["use_case"].execute(context["tenant_id"]))


@then(parsers.parse("應回傳 {count:d} 筆對話"))
def verify_conversation_count(result, count):
    assert len(result) == count


# ── Scenario 5: bot 歸屬驗證 ──


@given(
    parsers.parse(
        '租戶 "{tenant_id}" 嘗試使用屬於 "{bot_tenant_id}" 的 bot "{bot_id}"'
    )
)
def setup_cross_tenant_bot(context, tenant_id, bot_tenant_id, bot_id):
    mock_conv_repo = AsyncMock()
    mock_conv_repo.find_by_id = AsyncMock(return_value=None)
    mock_conv_repo.save = AsyncMock()

    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(
        return_value=Bot(tenant_id=bot_tenant_id, name="Other Bot")
    )

    mock_agent = AsyncMock()

    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_conv_repo,
        bot_repository=mock_bot_repo,
    )
    context["command"] = SendMessageCommand(
        tenant_id=tenant_id, bot_id=bot_id, message="hi"
    )


@when("透過 Use Case 發送訊息")
def execute_send_with_cross_tenant_bot(context):
    try:
        _run(context["use_case"].execute(context["command"]))
        context["error"] = None
    except DomainException as e:
        context["error"] = e


@then(parsers.parse('應拋出 DomainException 且訊息包含 "{expected_msg}"'))
def verify_domain_exception(context, expected_msg):
    assert context["error"] is not None, "Expected DomainException but none was raised"
    assert expected_msg in context["error"].message
