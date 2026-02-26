"""提交回饋 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackCommand,
    SubmitFeedbackUseCase,
)
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/conversation/submit_feedback.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


def _setup_conversation_and_repos(context, conv_id="conv-1"):
    conversation = Conversation(
        id=ConversationId(value=conv_id),
        tenant_id="tenant-1",
    )
    conversation.messages.append(
        Message(
            id=MessageId(value="msg-1"),
            conversation_id=conv_id,
            role="assistant",
            content="這是一則回答",
        )
    )

    mock_conv_repo = AsyncMock(spec=ConversationRepository)
    mock_conv_repo.find_by_id = AsyncMock(return_value=conversation)

    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)
    mock_feedback_repo.find_by_message_id = AsyncMock(return_value=None)
    mock_feedback_repo.save = AsyncMock(return_value=None)
    mock_feedback_repo.update = AsyncMock(return_value=None)

    context["use_case"] = SubmitFeedbackUseCase(
        feedback_repository=mock_feedback_repo,
        conversation_repository=mock_conv_repo,
    )
    context["mock_feedback_repo"] = mock_feedback_repo
    context["mock_conv_repo"] = mock_conv_repo


@given('租戶 "tenant-1" 有一段對話 "conv-1" 包含 assistant 訊息 "msg-1"')
def setup_conversation_with_message(context):
    _setup_conversation_and_repos(context)


@given('訊息 "msg-1" 已有一筆 "thumbs_up" 回饋')
def setup_existing_feedback_thumbs_up(context):
    _setup_conversation_and_repos(context)
    existing_feedback = Feedback(
        id=FeedbackId(),
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-1",
        user_id=None,
        channel=Channel.WEB,
        rating=Rating.THUMBS_UP,
        comment=None,
    )
    context["mock_feedback_repo"].find_by_message_id = AsyncMock(
        return_value=existing_feedback
    )


@given('訊息 "msg-2" 已有一筆 "thumbs_down" 回饋且評論為 "答案不正確"')
def setup_existing_feedback_with_comment(context):
    _setup_conversation_and_repos(context)
    existing_feedback = Feedback(
        id=FeedbackId(),
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-2",
        user_id=None,
        channel=Channel.WEB,
        rating=Rating.THUMBS_DOWN,
        comment="答案不正確",
    )
    context["mock_feedback_repo"].find_by_message_id = AsyncMock(
        return_value=existing_feedback
    )


@given('租戶 "tenant-1" 沒有對話 "conv-unknown"')
def setup_missing_conversation(context):
    mock_conv_repo = AsyncMock(spec=ConversationRepository)
    mock_conv_repo.find_by_id = AsyncMock(return_value=None)

    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)

    context["use_case"] = SubmitFeedbackUseCase(
        feedback_repository=mock_feedback_repo,
        conversation_repository=mock_conv_repo,
    )


@when('我對訊息 "msg-1" 提交 "thumbs_up" 回饋，通路為 "web"')
def submit_positive_feedback(context):
    command = SubmitFeedbackCommand(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-1",
        channel="web",
        rating="thumbs_up",
    )
    context["result"] = _run(context["use_case"].execute(command))


@when('我對訊息 "msg-1" 提交 "thumbs_down" 回饋，評論為 "答案不正確"')
def submit_negative_feedback_with_comment(context):
    command = SubmitFeedbackCommand(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-1",
        channel="web",
        rating="thumbs_down",
        comment="答案不正確",
    )
    context["result"] = _run(context["use_case"].execute(command))


@when('我對訊息 "msg-1" 再次提交 "thumbs_down" 回饋')
def submit_updated_feedback(context):
    command = SubmitFeedbackCommand(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-1",
        channel="web",
        rating="thumbs_down",
    )
    context["result"] = _run(context["use_case"].execute(command))


@when('我對訊息 "msg-2" 再次提交 "thumbs_up" 回饋，評論為 "後來覺得還行"')
def submit_changed_mind_feedback(context):
    command = SubmitFeedbackCommand(
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-2",
        channel="web",
        rating="thumbs_up",
        comment="後來覺得還行",
    )
    context["result"] = _run(context["use_case"].execute(command))


@when('我對對話 "conv-unknown" 的訊息 "msg-1" 提交回饋')
def submit_feedback_missing_conversation(context):
    command = SubmitFeedbackCommand(
        tenant_id="tenant-1",
        conversation_id="conv-unknown",
        message_id="msg-1",
        channel="web",
        rating="thumbs_up",
    )
    try:
        _run(context["use_case"].execute(command))
        context["error"] = None
    except EntityNotFoundError as e:
        context["error"] = e


@then("回饋應成功建立")
def verify_feedback_created(context):
    assert context["result"] is not None
    assert isinstance(context["result"], Feedback)


@then("回饋應成功更新")
def verify_feedback_updated(context):
    assert context["result"] is not None
    assert isinstance(context["result"], Feedback)
    context["mock_feedback_repo"].update.assert_called_once()


@then('回饋的 rating 應為 "thumbs_up"')
def verify_rating_thumbs_up(context):
    assert context["result"].rating == Rating.THUMBS_UP


@then('回饋的 rating 應為 "thumbs_down"')
def verify_rating_thumbs_down(context):
    assert context["result"].rating == Rating.THUMBS_DOWN


@then('回饋的 comment 應為 "答案不正確"')
def verify_comment_incorrect(context):
    assert context["result"].comment == "答案不正確"


@then('回饋的 comment 應為 "後來覺得還行"')
def verify_comment_changed_mind(context):
    assert context["result"].comment == "後來覺得還行"


@then("應拋出實體未找到錯誤")
def verify_not_found_error(context):
    assert isinstance(context["error"], EntityNotFoundError)
