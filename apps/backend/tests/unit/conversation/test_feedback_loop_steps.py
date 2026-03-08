"""Feedback 閉環品質標記 BDD Step Definitions"""

from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.conversation.get_retrieval_quality_use_case import (
    GetRetrievalQualityUseCase,
)
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)

scenarios("unit/conversation/feedback_loop.feature")


@pytest.fixture
def context():
    return {}


@given("一個已建立的 Feedback")
def setup_existing_feedback(context):
    context["feedback"] = Feedback(
        id=FeedbackId(value="fb-1"),
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-1",
        user_id=None,
        channel=Channel.WEB,
        rating=Rating.THUMBS_UP,
        comment=None,
    )


@given("一個新建立的 Feedback")
def setup_new_feedback(context):
    context["feedback"] = Feedback(
        id=FeedbackId(value="fb-2"),
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-2",
        user_id=None,
        channel=Channel.WEB,
        rating=Rating.THUMBS_UP,
        comment=None,
    )


@given('一個 rating 為 "thumbs_down" 的 Feedback')
def setup_negative_feedback(context):
    context["feedback"] = Feedback(
        id=FeedbackId(value="fb-3"),
        tenant_id="tenant-1",
        conversation_id="conv-1",
        message_id="msg-3",
        user_id=None,
        channel=Channel.WEB,
        rating=Rating.THUMBS_DOWN,
        comment="答案不正確",
    )
    mock_repo = AsyncMock(spec=FeedbackRepository)
    context["use_case"] = GetRetrievalQualityUseCase(
        feedback_repository=mock_repo,
    )


@when('設定 retrieval_quality 為 "low"')
def set_retrieval_quality_low(context):
    context["feedback"].retrieval_quality = "low"


@when("分析檢索品質")
def analyze_chunk_quality(context):
    result = context["use_case"].analyze_chunk_quality(
        [context["feedback"]]
    )
    context["quality_result"] = result


@then('Feedback 的 retrieval_quality 應為 "low"')
def verify_retrieval_quality_low(context):
    assert context["feedback"].retrieval_quality == "low"


@then("Feedback 的 retrieval_quality 應為 None")
def verify_retrieval_quality_none(context):
    assert context["feedback"].retrieval_quality is None


@then("應標記相關 chunks 為低品質")
def verify_low_quality_chunks(context):
    result = context["quality_result"]
    assert len(result) == 1
    assert result[0].quality == "low"
    assert result[0].feedback_id == "fb-3"
    assert result[0].message_id == "msg-3"
    assert result[0].conversation_id == "conv-1"
