"""回饋統計 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.conversation.get_feedback_stats_use_case import (
    GetFeedbackStatsUseCase,
)
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import Rating

scenarios("unit/conversation/feedback_stats.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


@given('租戶 "tenant-1" 有 10 筆回饋，其中 7 筆正面 3 筆負面')
def setup_feedback_data(context):
    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)

    async def mock_count(tenant_id, rating=None):
        if rating is None:
            return 10
        if rating == Rating.THUMBS_UP:
            return 7
        return 3

    mock_feedback_repo.count_by_tenant_and_rating = AsyncMock(
        side_effect=mock_count
    )

    context["use_case"] = GetFeedbackStatsUseCase(
        feedback_repository=mock_feedback_repo,
    )


@given('租戶 "tenant-1" 沒有任何回饋')
def setup_no_feedback(context):
    mock_feedback_repo = AsyncMock(spec=FeedbackRepository)
    mock_feedback_repo.count_by_tenant_and_rating = AsyncMock(return_value=0)

    context["use_case"] = GetFeedbackStatsUseCase(
        feedback_repository=mock_feedback_repo,
    )


@when('我查詢租戶 "tenant-1" 的回饋統計')
def query_feedback_stats(context):
    context["result"] = _run(context["use_case"].execute("tenant-1"))


@then("總數應為 10")
def verify_total_10(context):
    assert context["result"].total == 10


@then("總數應為 0")
def verify_total_0(context):
    assert context["result"].total == 0


@then("滿意率應為 70.0")
def verify_satisfaction_70(context):
    assert context["result"].satisfaction_rate == 70.0


@then("滿意率應為 0.0")
def verify_satisfaction_0(context):
    assert context["result"].satisfaction_rate == 0.0
