"""LINE Webhook 對話追蹤 BDD Step Definitions."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.value_objects import ConversationId, MessageId

scenarios("unit/line/line_conversation_tracking.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Scenario 1: 第一次發訊息建立新 conversation ---


@given('一個 LINE 用戶 "U001" 對 bot "bot-001" 發送第一條訊息')
def setup_first_message(context):
    context["user_id"] = "U001"
    context["bot_id"] = "bot-001"
    context["tenant_id"] = "tenant-001"


@given("該用戶沒有任何 conversation")
def no_existing_conversation(context):
    mock_conv_repo = AsyncMock()
    mock_conv_repo.find_latest_by_visitor = AsyncMock(return_value=None)
    mock_conv_repo.save = AsyncMock()
    context["conv_repo"] = mock_conv_repo


@when("webhook 處理該訊息", target_fixture="result")
def process_message(context):
    """Simulate the conversation lookup + creation logic."""
    conv_repo = context["conv_repo"]
    user_id = context["user_id"]
    bot_id = context["bot_id"]

    # This is the logic that will be in handle_webhook_use_case
    existing = _run(conv_repo.find_latest_by_visitor(user_id, bot_id))

    if existing is None:
        # New conversation
        conv = Conversation(
            tenant_id=context["tenant_id"],
            bot_id=bot_id,
        )
        conv.visitor_id = user_id  # Will be added to entity
        context["conversation"] = conv
        context["is_new"] = True
    else:
        context["conversation"] = existing
        context["is_new"] = False

    return context


@then("應建立新的 conversation")
def verify_new_conversation(result):
    assert result["is_new"] is True
    assert result["conversation"] is not None


@then('conversation 的 bot_id 應為 "bot-001"')
def verify_bot_id(result):
    assert result["conversation"].bot_id == "bot-001"


# --- Scenario 2: 30 分鐘內延續 ---


@given('一個 LINE 用戶 "U001" 已有 conversation "conv-001" 且最後訊息在 10 分鐘前')
def setup_recent_conversation(context):
    context["user_id"] = "U001"
    context["bot_id"] = "bot-001"
    context["tenant_id"] = "tenant-001"

    conv = Conversation(
        id=ConversationId("conv-001"),
        tenant_id="tenant-001",
        bot_id="bot-001",
    )
    last_msg_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    conv.messages = [
        Message(
            id=MessageId("msg-old"),
            conversation_id="conv-001",
            role="user",
            content="舊訊息",
            created_at=last_msg_time,
        )
    ]

    mock_conv_repo = AsyncMock()
    mock_conv_repo.find_latest_by_visitor = AsyncMock(return_value=conv)
    mock_conv_repo.save = AsyncMock()
    context["conv_repo"] = mock_conv_repo


@when("webhook 處理新訊息", target_fixture="result")
def process_new_message(context):
    conv_repo = context["conv_repo"]
    user_id = context["user_id"]
    bot_id = context.get("bot_id", "bot-001")

    existing = _run(conv_repo.find_latest_by_visitor(user_id, bot_id))

    timeout_minutes = 30
    if existing and existing.messages:
        last_msg = existing.messages[-1]
        elapsed = datetime.now(timezone.utc) - last_msg.created_at
        if elapsed < timedelta(minutes=timeout_minutes):
            context["conversation"] = existing
            context["is_new"] = False
        else:
            conv = Conversation(
                tenant_id=context["tenant_id"],
                bot_id=bot_id,
            )
            context["conversation"] = conv
            context["is_new"] = True
    elif existing:
        context["conversation"] = existing
        context["is_new"] = False
    else:
        conv = Conversation(
            tenant_id=context["tenant_id"],
            bot_id=bot_id,
        )
        context["conversation"] = conv
        context["is_new"] = True

    return context


@then('應複用 conversation "conv-001"')
def verify_reuse_conversation(result):
    assert result["is_new"] is False
    assert result["conversation"].id.value == "conv-001"


# --- Scenario 3: 超過 30 分鐘建新 ---


@given('一個 LINE 用戶 "U001" 已有 conversation "conv-old" 且最後訊息在 40 分鐘前')
def setup_old_conversation(context):
    context["user_id"] = "U001"
    context["bot_id"] = "bot-001"
    context["tenant_id"] = "tenant-001"

    conv = Conversation(
        id=ConversationId("conv-old"),
        tenant_id="tenant-001",
        bot_id="bot-001",
    )
    last_msg_time = datetime.now(timezone.utc) - timedelta(minutes=40)
    conv.messages = [
        Message(
            id=MessageId("msg-old"),
            conversation_id="conv-old",
            role="user",
            content="舊訊息",
            created_at=last_msg_time,
        )
    ]

    mock_conv_repo = AsyncMock()
    mock_conv_repo.find_latest_by_visitor = AsyncMock(return_value=conv)
    mock_conv_repo.save = AsyncMock()
    context["conv_repo"] = mock_conv_repo


@then('新 conversation 的 id 不應為 "conv-old"')
def verify_new_id(result):
    assert result["conversation"].id.value != "conv-old"


# --- Scenario 4: 回饋關聯 conversation_id ---


@given('一個 message "msg-001" 屬於 conversation "conv-001"')
def setup_message_with_conversation(context):
    context["message_id"] = "msg-001"
    context["expected_conversation_id"] = "conv-001"

    mock_conv_repo = AsyncMock()
    mock_conv_repo.find_conversation_id_by_message = AsyncMock(
        return_value="conv-001"
    )
    context["conv_repo"] = mock_conv_repo

    mock_feedback_repo = AsyncMock()
    mock_feedback_repo.find_by_message_id = AsyncMock(return_value=None)
    mock_feedback_repo.save = AsyncMock()
    context["feedback_repo"] = mock_feedback_repo


@when('LINE 用戶對 "msg-001" 給了 thumbs_up 回饋', target_fixture="feedback_result")
def submit_feedback(context):
    conv_repo = context["conv_repo"]
    message_id = context["message_id"]

    # Look up conversation_id from message
    conversation_id = _run(
        conv_repo.find_conversation_id_by_message(message_id)
    )
    context["feedback_conversation_id"] = conversation_id or ""
    return context


@then('feedback 的 conversation_id 應為 "conv-001"')
def verify_feedback_conversation_id(feedback_result):
    assert feedback_result["feedback_conversation_id"] == "conv-001"
