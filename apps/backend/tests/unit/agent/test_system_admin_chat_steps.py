"""System Admin 跨租戶 Chat BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.shared.exceptions import DomainException

scenarios("unit/agent/system_admin_chat.feature")

SYSTEM_ADMIN_TENANT = "00000000-0000-0000-0000-000000000000"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# ── Scenario 1: System Admin 跨租戶成功 ──


@given(parsers.parse('系統管理員（tenant "{tenant_id}"）'))
def setup_system_admin(context, tenant_id):
    context["tenant_id"] = tenant_id
    context["role"] = "system_admin"


@given(parsers.parse('一個屬於租戶 "{bot_tenant_id}" 的 bot "{bot_id}"'))
def setup_bot(context, bot_tenant_id, bot_id):
    context["bot_tenant_id"] = bot_tenant_id
    context["bot_id"] = bot_id

    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(
        return_value=Bot(tenant_id=bot_tenant_id, name="Test Bot")
    )

    mock_conv_repo = AsyncMock()
    mock_conv_repo.find_by_id = AsyncMock(return_value=None)
    mock_conv_repo.save = AsyncMock()

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="ok", tool_calls=[], sources=[])
    )

    context["mock_bot_repo"] = mock_bot_repo
    context["mock_conv_repo"] = mock_conv_repo
    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_conv_repo,
        bot_repository=mock_bot_repo,
    )


@when("系統管理員透過該 Bot 發送訊息")
def system_admin_send_message(context):
    """System admin 用 bot 的 tenant_id（而非自己的 tenant_id）發送訊息"""
    # 模擬 router 層的 effective_tenant_id 邏輯：
    # system_admin 時使用 bot 的 tenant_id
    effective_tenant_id = context["bot_tenant_id"]

    command = SendMessageCommand(
        tenant_id=effective_tenant_id,
        bot_id=context["bot_id"],
        message="hello",
    )
    try:
        _run(context["use_case"].execute(command))
        context["error"] = None
    except DomainException as e:
        context["error"] = e


@then("訊息應使用 bot 所屬租戶的 tenant_id 發送")
def verify_effective_tenant_id(context):
    saved_conversation = context["mock_conv_repo"].save.call_args[0][0]
    assert saved_conversation.tenant_id == context["bot_tenant_id"]


@then("不應拋出 DomainException")
def verify_no_exception(context):
    assert context["error"] is None, f"Unexpected DomainException: {context.get('error')}"


# ── Scenario 2: 一般租戶跨租戶失敗（重用 conversation_bot_filter 的步驟） ──


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
