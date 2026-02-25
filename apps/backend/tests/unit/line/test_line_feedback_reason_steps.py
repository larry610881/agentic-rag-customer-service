"""LINE 回饋追問原因 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.domain.line.entity import LinePostbackEvent

scenarios("unit/line/line_feedback_reason.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_use_case(context):
    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)
    mock_feedback_repo.find_by_message_id = AsyncMock(return_value=None)
    mock_feedback_repo.save = AsyncMock(return_value=None)
    mock_feedback_repo.update_tags = AsyncMock(return_value=None)

    mock_line_service = AsyncMock()

    context["mock_feedback_repo"] = mock_feedback_repo
    context["mock_line_service"] = mock_line_service
    context["use_case"] = HandleWebhookUseCase(
        agent_service=AsyncMock(),
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        feedback_repository=mock_feedback_repo,
    )


@given("一個 LINE 使用者按下 thumbs_down")
def setup_thumbs_down(context):
    _make_use_case(context)
    context["postback_event"] = LinePostbackEvent(
        reply_token="token-001",
        user_id="U1234567890",
        postback_data="feedback:msg-001:thumbs_down",
        timestamp=1700000000000,
    )


@given("一個 LINE 使用者按下 thumbs_up")
def setup_thumbs_up(context):
    _make_use_case(context)
    context["postback_event"] = LinePostbackEvent(
        reply_token="token-002",
        user_id="U1234567890",
        postback_data="feedback:msg-002:thumbs_up",
        timestamp=1700000000000,
    )


@given(parsers.parse('一個已回饋 thumbs_down 的訊息 "{msg_id}"'))
def setup_existing_feedback(context, msg_id):
    _make_use_case(context)
    context["postback_event"] = LinePostbackEvent(
        reply_token="token-003",
        user_id="U1234567890",
        postback_data=f"feedback_reason:{msg_id}:incorrect",
        timestamp=1700000000000,
    )


@when("系統處理該 postback 事件")
def process_postback(context):
    _run(
        context["use_case"].handle_postback(
            context["postback_event"],
            "tenant-1",
            line_service=context["mock_line_service"],
        )
    )


@when(parsers.parse('使用者選擇原因 "{tag}"'))
def select_reason(context, tag):
    _run(
        context["use_case"].handle_postback(
            context["postback_event"],
            "tenant-1",
            line_service=context["mock_line_service"],
        )
    )


@then("應儲存 thumbs_down 回饋")
def verify_thumbs_down_saved(context):
    context["mock_feedback_repo"].save.assert_called_once()
    saved = context["mock_feedback_repo"].save.call_args[0][0]
    assert saved.rating == Rating.THUMBS_DOWN


@then("應儲存 thumbs_up 回饋")
def verify_thumbs_up_saved(context):
    context["mock_feedback_repo"].save.assert_called_once()
    saved = context["mock_feedback_repo"].save.call_args[0][0]
    assert saved.rating == Rating.THUMBS_UP


@then("應呼叫 reply_with_reason_options")
def verify_reason_options_called(context):
    context["mock_line_service"].reply_with_reason_options.assert_called_once()


@then(parsers.parse('該回饋的 tags 應包含 "{tag}"'))
def verify_tags_contain(context, tag):
    context["mock_feedback_repo"].update_tags.assert_called_once()
    call_args = context["mock_feedback_repo"].update_tags.call_args
    assert tag in call_args[0][1]


@then("應回覆確認訊息")
def verify_confirm_reply(context):
    context["mock_line_service"].reply_text.assert_called_once()
    call_args = context["mock_line_service"].reply_text.call_args[0]
    assert "回饋" in call_args[1] or "改進" in call_args[1]


@then("應回覆感謝訊息")
def verify_thanks_reply(context):
    context["mock_line_service"].reply_text.assert_called_once()
    call_args = context["mock_line_service"].reply_text.call_args[0]
    assert "感謝" in call_args[1] or "回饋" in call_args[1]
