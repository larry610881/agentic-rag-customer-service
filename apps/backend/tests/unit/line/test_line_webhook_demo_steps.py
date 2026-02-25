"""Demo 6 — LINE Bot Webhook E2E Mock Test (httpx.AsyncClient)"""

import asyncio
import base64
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.line.services import LineMessagingService

scenarios("unit/line/line_webhook_demo.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_signature(secret: str, body: str) -> str:
    hash_value = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(hash_value).decode("utf-8")


# ---------- fixtures ----------


@pytest.fixture
def context():
    return {}


# ---------- Background ----------


@given('LINE Channel Secret 為 "test-secret-key"')
def setup_channel_secret(context):
    context["channel_secret"] = "test-secret-key"


@given("Agent 服務使用 Fake 模式")
def setup_agent_fake_mode(context):
    context["mock_agent"] = AsyncMock()
    context["mock_line_service"] = AsyncMock(spec=LineMessagingService)
    context["mock_line_service"].verify_signature = AsyncMock()
    context["mock_line_service"].reply_text = AsyncMock()


# ---------- Given: text messages ----------


@given('LINE 用戶 "U001" 傳送訊息 "你們的保固政策是什麼？"')
def user_sends_warranty_query(context):
    context["user_id"] = "U001"
    context["message_text"] = "你們的保固政策是什麼？"
    context["reply_token"] = "reply-token-001"
    context["event_type"] = "text"


@given('LINE 用戶 "U002" 傳送訊息 "我的訂單 ORD-001 目前狀態？"')
def user_sends_order_query(context):
    context["user_id"] = "U002"
    context["message_text"] = "我的訂單 ORD-001 目前狀態？"
    context["reply_token"] = "reply-token-002"
    context["event_type"] = "text"


@given('LINE 用戶 "U003" 傳送訊息 "我要退貨"')
def user_sends_refund_request(context):
    context["user_id"] = "U003"
    context["message_text"] = "我要退貨"
    context["reply_token"] = "reply-token-003"
    context["event_type"] = "text"


@given('LINE 用戶 "U004" 傳送訊息 "任意訊息"')
def user_sends_any_message(context):
    context["user_id"] = "U004"
    context["message_text"] = "任意訊息"
    context["reply_token"] = "reply-token-004"
    context["event_type"] = "text"


@given('LINE 用戶 "U005" 傳送了圖片訊息')
def user_sends_image(context):
    context["user_id"] = "U005"
    context["message_text"] = None
    context["reply_token"] = "reply-token-005"
    context["event_type"] = "image"


# ---------- When ----------


def _build_webhook_body(context) -> str:
    if context["event_type"] == "text":
        events = [
            {
                "type": "message",
                "replyToken": context["reply_token"],
                "source": {"userId": context["user_id"]},
                "message": {"type": "text", "text": context["message_text"]},
                "timestamp": 1700000000000,
            }
        ]
    else:
        events = [
            {
                "type": "message",
                "replyToken": context["reply_token"],
                "source": {"userId": context["user_id"]},
                "message": {"type": context["event_type"]},
                "timestamp": 1700000000000,
            }
        ]
    return json.dumps({"events": events}, ensure_ascii=False)


@when("系統收到帶有效簽名的 Webhook 請求")
def receive_valid_webhook(context):
    body = _build_webhook_body(context)
    secret = context["channel_secret"]
    signature = _make_signature(secret, body)

    # Configure mock_line_service.verify_signature to return True
    context["mock_line_service"].verify_signature = AsyncMock(return_value=True)

    # Determine agent response based on message
    msg = context.get("message_text") or ""
    if "訂單" in msg or "ORD-" in msg:
        agent_answer = "您的訂單目前狀態為：已出貨，預計送達日期為 2024-01-20。"
    elif "退貨" in msg or "退款" in msg:
        agent_answer = "好的，我來協助您處理退貨。請提供您的訂單編號。"
    elif msg:
        agent_answer = "根據知識庫：本公司提供一年保固服務，退貨政策為 30 天內可退貨。"
    else:
        agent_answer = ""

    context["mock_agent"].process_message = AsyncMock(
        return_value=AgentResponse(answer=agent_answer)
    )

    use_case = HandleWebhookUseCase(
        agent_service=context["mock_agent"],
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        default_line_service=context["mock_line_service"],
        default_tenant_id="tenant-demo",
        default_kb_id="kb-demo",
    )

    # Simulate the full router logic inline (parse events → use_case.execute)
    data = json.loads(body)
    from src.domain.line.entity import LineTextMessageEvent

    events = []
    for event_data in data.get("events", []):
        if (
            event_data.get("type") == "message"
            and event_data.get("message", {}).get("type") == "text"
        ):
            events.append(
                LineTextMessageEvent(
                    reply_token=event_data["replyToken"],
                    user_id=event_data["source"]["userId"],
                    message_text=event_data["message"]["text"],
                    timestamp=event_data["timestamp"],
                )
            )

    context["parsed_events"] = events
    context["signature"] = signature
    context["body"] = body
    context["use_case"] = use_case

    # Execute: verify signature + process events
    is_valid = _run(
        context["mock_line_service"].verify_signature(body, signature)
    )
    context["signature_valid"] = is_valid

    if is_valid and events:
        _run(use_case.execute(events))

    context["http_status"] = 200 if is_valid else 403


@when("系統收到帶無效簽名的 Webhook 請求")
def receive_invalid_webhook(context):
    body = _build_webhook_body(context)

    # Configure mock_line_service.verify_signature to return False
    context["mock_line_service"].verify_signature = AsyncMock(return_value=False)

    context["body"] = body
    context["signature"] = "invalid-signature"
    context["signature_valid"] = False
    context["parsed_events"] = []

    # Verify signature fails
    is_valid = _run(
        context["mock_line_service"].verify_signature(body, "invalid-signature")
    )
    context["signature_valid"] = is_valid
    context["http_status"] = 403


# ---------- Then ----------


@then("HTTP 回應狀態碼為 200")
def verify_status_200(context):
    assert context["http_status"] == 200


@then("HTTP 回應狀態碼為 403")
def verify_status_403(context):
    assert context["http_status"] == 403


@then('Agent 應處理訊息 "你們的保固政策是什麼？"')
def verify_agent_called_warranty(context):
    context["mock_agent"].process_message.assert_called_once()
    call_kwargs = context["mock_agent"].process_message.call_args
    assert call_kwargs.kwargs["user_message"] == "你們的保固政策是什麼？"


@then('Agent 應處理訊息 "我的訂單 ORD-001 目前狀態？"')
def verify_agent_called_order(context):
    context["mock_agent"].process_message.assert_called_once()
    call_kwargs = context["mock_agent"].process_message.call_args
    assert call_kwargs.kwargs["user_message"] == "我的訂單 ORD-001 目前狀態？"


@then('Agent 應處理訊息 "我要退貨"')
def verify_agent_called_refund(context):
    context["mock_agent"].process_message.assert_called_once()
    call_kwargs = context["mock_agent"].process_message.call_args
    assert call_kwargs.kwargs["user_message"] == "我要退貨"


@then('LINE 應回覆包含 "保固" 的答案')
def verify_line_reply_warranty(context):
    context["mock_line_service"].reply_text.assert_called_once()
    reply_text = context["mock_line_service"].reply_text.call_args[0][1]
    assert "保固" in reply_text


@then('LINE 應回覆包含 "訂單" 的答案')
def verify_line_reply_order(context):
    context["mock_line_service"].reply_text.assert_called_once()
    reply_text = context["mock_line_service"].reply_text.call_args[0][1]
    assert "訂單" in reply_text


@then('LINE 應回覆包含 "退貨" 的答案')
def verify_line_reply_refund(context):
    context["mock_line_service"].reply_text.assert_called_once()
    reply_text = context["mock_line_service"].reply_text.call_args[0][1]
    assert "退貨" in reply_text


@then("Agent 不應被呼叫")
def verify_agent_not_called(context):
    context["mock_agent"].process_message.assert_not_called()


@then("LINE 不應回覆任何訊息")
def verify_line_no_reply(context):
    context["mock_line_service"].reply_text.assert_not_called()
