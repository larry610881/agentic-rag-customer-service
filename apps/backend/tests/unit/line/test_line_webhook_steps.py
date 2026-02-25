"""LINE Webhook BDD Step Definitions"""

import asyncio
import base64
import hashlib
import hmac
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.line.entity import LineTextMessageEvent

scenarios("unit/line/line_webhook.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Scenario: 接收文字訊息並回覆 Agent 答案 ---


@given('LINE 用戶 "U1234567890" 發送了文字訊息 "我想查詢退貨政策"')
def line_user_sends_text_return_policy(context):
    context["events"] = [
        LineTextMessageEvent(
            reply_token="token-abc",
            user_id="U1234567890",
            message_text="我想查詢退貨政策",
            timestamp=1700000000000,
        )
    ]


@given('Agent 服務回覆 "根據退貨政策，您可以在30天內退貨。"')
def agent_replies_return_policy(context):
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(
            answer="根據退貨政策，您可以在30天內退貨。",
        )
    )
    mock_line_service = AsyncMock()
    context["mock_agent"] = mock_agent
    context["mock_line_service"] = mock_line_service
    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        line_messaging_service=mock_line_service,
        default_tenant_id="tenant-001",
        default_kb_id="kb-001",
    )


@when("系統處理 LINE Webhook 事件")
def process_webhook(context):
    _run(context["use_case"].execute(context["events"]))


@then('系統應透過 LINE API 回覆 "根據退貨政策，您可以在30天內退貨。"')
def verify_reply_return_policy(context):
    context["mock_line_service"].reply_text.assert_called_once_with(
        "token-abc", "根據退貨政策，您可以在30天內退貨。"
    )


# --- Scenario: 驗證 LINE Webhook 簽名 ---


@given("一個帶有有效簽名的 Webhook 請求")
def valid_signature_request(context):
    from src.infrastructure.line.line_messaging_service import (
        HttpxLineMessagingService,
    )

    secret = "test-channel-secret"
    context["body"] = '{"events":[]}'
    hash_value = hmac.new(
        secret.encode("utf-8"),
        context["body"].encode("utf-8"),
        hashlib.sha256,
    ).digest()
    context["signature"] = base64.b64encode(hash_value).decode("utf-8")
    context["service"] = HttpxLineMessagingService(
        channel_secret=secret,
        channel_access_token="test-token",
    )


@when("系統驗證簽名")
def verify_signature(context):
    context["result"] = _run(
        context["service"].verify_signature(context["body"], context["signature"])
    )


@then("驗證應通過")
def signature_should_pass(context):
    assert context["result"] is True


# --- Scenario: 拒絕無效簽名的 Webhook 請求 ---


@given("一個帶有無效簽名的 Webhook 請求")
def invalid_signature_request(context):
    from src.infrastructure.line.line_messaging_service import (
        HttpxLineMessagingService,
    )

    secret = "test-channel-secret"
    context["body"] = '{"events":[]}'
    context["signature"] = "invalid-signature"
    context["service"] = HttpxLineMessagingService(
        channel_secret=secret,
        channel_access_token="test-token",
    )


@then("驗證應失敗")
def signature_should_fail(context):
    assert context["result"] is False


# --- Scenario: 忽略非文字訊息事件 ---


@given("LINE 用戶發送了一個圖片訊息事件")
def line_user_sends_image(context):
    context["events"] = []


@given("Agent 服務已準備就緒")
def agent_service_ready(context):
    mock_agent = AsyncMock()
    mock_line_service = AsyncMock()
    context["mock_agent"] = mock_agent
    context["mock_line_service"] = mock_line_service
    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        line_messaging_service=mock_line_service,
        default_tenant_id="tenant-001",
        default_kb_id="kb-001",
    )


@then("系統不應呼叫 Agent 服務")
def agent_not_called(context):
    context["mock_agent"].process_message.assert_not_called()


@then("系統不應透過 LINE API 回覆")
def line_reply_not_called(context):
    context["mock_line_service"].reply_text.assert_not_called()


# --- Scenario: Agent 回答包含工具調用資訊 ---


@given('LINE 用戶 "U9876543210" 發送了文字訊息 "退貨流程是什麼？"')
def line_user_sends_rag_query(context):
    context["events"] = [
        LineTextMessageEvent(
            reply_token="token-xyz",
            user_id="U9876543210",
            message_text="退貨流程是什麼？",
            timestamp=1700000001000,
        )
    ]


@given(
    'Agent 服務回覆 "30 天內可辦理退貨。" 並包含工具調用 "rag_query"'
)
def agent_replies_with_tool_call(context):
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(
            answer="30 天內可辦理退貨。",
            tool_calls=[{"name": "rag_query", "reasoning": "知識庫查詢"}],
        )
    )
    mock_line_service = AsyncMock()
    context["mock_agent"] = mock_agent
    context["mock_line_service"] = mock_line_service
    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        line_messaging_service=mock_line_service,
        default_tenant_id="tenant-001",
        default_kb_id="kb-001",
    )


@then('系統應透過 LINE API 回覆 "30 天內可辦理退貨。"')
def verify_reply_rag_answer(context):
    context["mock_line_service"].reply_text.assert_called_once_with(
        "token-xyz", "30 天內可辦理退貨。"
    )
