"""LINE Webhook Bot 路由 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.line.entity import LineTextMessageEvent

scenarios("unit/line/line_webhook_routing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Scenario: 新端點接收帶 Bot ID 的 Webhook 並呼叫 execute_for_bot ---


@given(parsers.parse('Bot "{bot_id}" 已設定且返回有效 LINE 服務'))
def bot_configured_with_line(context, bot_id):
    bot = Bot(
        tenant_id="tenant-route",
        name="Route Bot",
        line_channel_secret="secret-route",
        line_channel_access_token="token-route",
        knowledge_base_ids=["kb-route"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)

    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="OK")
    )

    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
    )
    context["mock_bot_repo"] = mock_bot_repo
    context["bot_id"] = bot_id


@when(parsers.parse('系統收到發往 "{path}" 的 Webhook'))
def receive_webhook_at_path(context, path):
    bot_id = path.rsplit("/", 1)[-1]
    body_text = '{"events":[{"type":"message","replyToken":"tk","source":{"userId":"U1"},"message":{"type":"text","text":"hi"},"timestamp":1}]}'
    _run(
        context["use_case"].execute_for_bot(
            bot_id, body_text, "sig"
        )
    )


@then(parsers.parse('應呼叫 execute_for_bot 並傳入 Bot ID "{bot_id}"'))
def verify_execute_for_bot_called(context, bot_id):
    context["mock_bot_repo"].find_by_id.assert_called_once_with(bot_id)


# --- Scenario: 舊端點仍使用預設設定呼叫 execute ---


@given("系統有預設 LINE 服務設定")
def system_with_default_config(context):
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="default reply")
    )
    mock_line_service = AsyncMock()

    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        default_line_service=mock_line_service,
        default_tenant_id="tenant-default",
        default_kb_id="kb-default",
    )
    context["mock_agent"] = mock_agent
    context["mock_line_service"] = mock_line_service


@when(parsers.parse('系統收到發往 "{path}" 的舊端點 Webhook'))
def receive_webhook_legacy(context, path):
    events = [
        LineTextMessageEvent(
            reply_token="tk-legacy",
            user_id="U-legacy",
            message_text="hello",
            timestamp=1,
        )
    ]
    _run(context["use_case"].execute(events))


@then("應呼叫 execute 並使用預設設定")
def verify_execute_called_with_defaults(context):
    context["mock_agent"].process_message.assert_called_once()
    call_kwargs = context["mock_agent"].process_message.call_args
    assert call_kwargs.kwargs["tenant_id"] == "tenant-default"
    assert call_kwargs.kwargs["kb_ids"] == ["kb-default"]
    context["mock_line_service"].reply_with_quick_reply.assert_called_once()
    call_args = context["mock_line_service"].reply_with_quick_reply.call_args[0]
    assert call_args[0] == "tk-legacy"
    assert call_args[1] == "default reply"
