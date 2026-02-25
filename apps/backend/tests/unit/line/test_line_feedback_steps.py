"""LINE 回饋收集 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.line.entity import LinePostbackEvent

scenarios("unit/line/line_feedback.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


@given('LINE Bot 收到一則 postback 事件，data 為 "feedback:msg-abc:thumbs_up"')
def setup_positive_postback(context):
    context["postback_event"] = LinePostbackEvent(
        reply_token="token-fb-001",
        user_id="U1234567890",
        postback_data="feedback:msg-abc:thumbs_up",
        timestamp=1700000000000,
    )
    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)
    mock_feedback_repo.find_by_message_id = AsyncMock(return_value=None)
    mock_feedback_repo.save = AsyncMock(return_value=None)

    context["mock_feedback_repo"] = mock_feedback_repo
    context["use_case"] = HandleWebhookUseCase(
        agent_service=AsyncMock(),
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        feedback_repository=mock_feedback_repo,
    )


@given('LINE Bot 收到一則 postback 事件，data 為 "feedback:msg-abc:thumbs_down"')
def setup_negative_postback(context):
    context["postback_event"] = LinePostbackEvent(
        reply_token="token-fb-002",
        user_id="U1234567890",
        postback_data="feedback:msg-abc:thumbs_down",
        timestamp=1700000000000,
    )
    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)
    mock_feedback_repo.find_by_message_id = AsyncMock(return_value=None)
    mock_feedback_repo.save = AsyncMock(return_value=None)

    context["mock_feedback_repo"] = mock_feedback_repo
    context["use_case"] = HandleWebhookUseCase(
        agent_service=AsyncMock(),
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        feedback_repository=mock_feedback_repo,
    )


@given('LINE Bot 收到一則 postback 事件，data 為 "invalid_data"')
def setup_invalid_postback(context):
    context["postback_event"] = LinePostbackEvent(
        reply_token="token-fb-003",
        user_id="U1234567890",
        postback_data="invalid_data",
        timestamp=1700000000000,
    )
    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)

    context["mock_feedback_repo"] = mock_feedback_repo
    context["use_case"] = HandleWebhookUseCase(
        agent_service=AsyncMock(),
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        feedback_repository=mock_feedback_repo,
    )


@when("系統處理該 postback 事件")
def process_postback(context):
    _run(
        context["use_case"].handle_postback(
            context["postback_event"], "tenant-1"
        )
    )


@then('應建立一筆 rating 為 "thumbs_up" 的回饋')
def verify_thumbs_up_feedback(context):
    context["mock_feedback_repo"].save.assert_called_once()
    saved_feedback = context["mock_feedback_repo"].save.call_args[0][0]
    assert saved_feedback.rating.value == "thumbs_up"


@then('應建立一筆 rating 為 "thumbs_down" 的回饋')
def verify_thumbs_down_feedback(context):
    context["mock_feedback_repo"].save.assert_called_once()
    saved_feedback = context["mock_feedback_repo"].save.call_args[0][0]
    assert saved_feedback.rating.value == "thumbs_down"


@then('回饋的 channel 應為 "line"')
def verify_line_channel(context):
    saved_feedback = context["mock_feedback_repo"].save.call_args[0][0]
    assert saved_feedback.channel.value == "line"


@then("應忽略該事件且不建立回饋")
def verify_no_feedback_created(context):
    context["mock_feedback_repo"].save.assert_not_called()
