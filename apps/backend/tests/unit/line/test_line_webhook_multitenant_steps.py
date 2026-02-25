"""LINE Webhook 多租戶 BDD Step Definitions"""

import asyncio
import base64
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.line.entity import LineTextMessageEvent

scenarios("unit/line/line_webhook_multitenant.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _build_use_case(context):
    """共用建構 HandleWebhookUseCase helper。"""
    mock_agent = context.get("mock_agent", AsyncMock())
    mock_bot_repo = context.get("mock_bot_repo", AsyncMock())
    mock_factory = context.get("mock_factory", MagicMock())
    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
    )
    return context["use_case"]


def _default_events():
    """建立一個預設的文字事件列表。"""
    return [
        LineTextMessageEvent(
            reply_token="token-mt-001",
            user_id="U-mt-user",
            message_text="測試訊息",
            timestamp=1700000000000,
        )
    ]


# --- Scenario: 透過 Bot ID 路由到正確租戶 ---


@given(
    parsers.parse('Bot "{bot_id}" 屬於租戶 "{tenant_id}" 且設定了 LINE Channel')
)
def bot_with_line_channel(context, bot_id, tenant_id):
    bot = Bot(
        tenant_id=tenant_id,
        name="Test Bot",
        line_channel_secret="secret-001",
        line_channel_access_token="token-001",
        knowledge_base_ids=["kb-default"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    context["mock_bot_repo"] = mock_bot_repo
    context["bot_id"] = bot_id
    context["bot"] = bot

    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)
    context["mock_factory"] = mock_factory
    context["mock_line_service"] = mock_line_service


@given(parsers.parse('Agent 服務已準備回覆 "{answer}"'))
def agent_ready_with_answer(context, answer):
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer=answer)
    )
    context["mock_agent"] = mock_agent
    context["expected_answer"] = answer


@when(parsers.parse('系統透過 Bot ID "{bot_id}" 處理 Webhook 事件'))
def process_webhook_for_bot(context, bot_id):
    _build_use_case(context)
    body_text = '{"events":[{"type":"message","message":{"type":"text","text":"測試訊息"}}]}'
    signature = "valid-sig"
    events = _default_events()
    try:
        _run(
            context["use_case"].execute_for_bot(
                bot_id, body_text, signature, events
            )
        )
        context["error"] = None
    except ValueError as e:
        context["error"] = e


@then(parsers.parse('Agent 應使用租戶 "{tenant_id}" 處理訊息'))
def verify_agent_tenant(context, tenant_id):
    context["mock_agent"].process_message.assert_called_once()
    call_kwargs = context["mock_agent"].process_message.call_args
    assert call_kwargs.kwargs["tenant_id"] == tenant_id


@then(parsers.parse('系統應透過 Bot 的 LINE 服務回覆 "{answer}"'))
def verify_bot_line_reply(context, answer):
    context["mock_line_service"].reply_with_quick_reply.assert_called_once()
    call_args = context["mock_line_service"].reply_with_quick_reply.call_args[0]
    assert call_args[0] == "token-mt-001"
    assert call_args[1] == answer


# --- Scenario: Bot 未設定 LINE Channel 時拒絕處理 ---


@given(
    parsers.parse(
        'Bot "{bot_id}" 屬於租戶 "{tenant_id}" 但未設定 LINE Channel'
    )
)
def bot_without_line_channel(context, bot_id, tenant_id):
    bot = Bot(
        tenant_id=tenant_id,
        name="No-LINE Bot",
        line_channel_secret=None,
        line_channel_access_token=None,
        knowledge_base_ids=["kb-default"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    context["mock_bot_repo"] = mock_bot_repo
    context["bot_id"] = bot_id


@then("應拋出 LINE Channel 未設定的錯誤")
def verify_channel_not_configured_error(context):
    assert context["error"] is not None
    assert "no LINE channel secret" in str(context["error"])


# --- Scenario: Bot ID 不存在時回傳錯誤 ---


@given(parsers.parse('Bot "{bot_id}" 不存在於系統中'))
def bot_not_found(context, bot_id):
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=None)
    context["mock_bot_repo"] = mock_bot_repo
    context["bot_id"] = bot_id


@then("應拋出 Bot 不存在的錯誤")
def verify_bot_not_found_error(context):
    assert context["error"] is not None
    assert "Bot not found" in str(context["error"])


# --- Scenario: 使用 Bot 的 Channel Secret 驗簽 ---


@given(parsers.parse('Bot "{bot_id}" 設定了 Channel Secret "{secret}"'))
def bot_with_specific_secret(context, bot_id, secret):
    bot = Bot(
        tenant_id="tenant-verify",
        name="Verify Bot",
        line_channel_secret=secret,
        line_channel_access_token="access-token-verify",
        knowledge_base_ids=["kb-verify"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    context["mock_bot_repo"] = mock_bot_repo
    context["bot_id"] = bot_id
    context["bot"] = bot
    context["channel_secret"] = secret


@given("Webhook 請求帶有正確的簽名")
def webhook_with_valid_signature(context):
    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)
    context["mock_factory"] = mock_factory
    context["mock_line_service"] = mock_line_service

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="OK")
    )
    context["mock_agent"] = mock_agent


@then("簽名驗證應使用 Bot 的 Channel Secret")
def verify_factory_called_with_secret(context):
    context["mock_factory"].create.assert_called_once_with(
        context["channel_secret"], "access-token-verify"
    )
    context["mock_line_service"].verify_signature.assert_called_once()


# --- Scenario: 使用 Bot 的知識庫和系統提示呼叫 Agent ---


@given(
    parsers.parse(
        'Bot "{bot_id}" 屬於租戶 "{tenant_id}" 且設定了知識庫 "{kb_ids}" 和系統提示 "{prompt}"'
    )
)
def bot_with_kb_and_prompt(context, bot_id, tenant_id, kb_ids, prompt):
    kb_list = kb_ids.split(",")
    bot = Bot(
        tenant_id=tenant_id,
        name="KB Bot",
        line_channel_secret="secret-kb",
        line_channel_access_token="token-kb",
        knowledge_base_ids=kb_list,
        system_prompt=prompt,
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    context["mock_bot_repo"] = mock_bot_repo
    context["bot_id"] = bot_id
    context["bot"] = bot

    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)
    context["mock_factory"] = mock_factory
    context["mock_line_service"] = mock_line_service


@then(parsers.parse('Agent 應使用知識庫 "{kb_ids}" 處理訊息'))
def verify_agent_kb_ids(context, kb_ids):
    expected = kb_ids.split(",")
    call_kwargs = context["mock_agent"].process_message.call_args
    assert call_kwargs.kwargs["kb_ids"] == expected


@then(parsers.parse('Agent 應使用系統提示 "{prompt}" 處理訊息'))
def verify_agent_system_prompt(context, prompt):
    call_kwargs = context["mock_agent"].process_message.call_args
    assert call_kwargs.kwargs["system_prompt"] == prompt
