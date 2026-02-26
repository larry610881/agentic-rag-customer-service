"""回饋統計 TTL 快取 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.get_feedback_stats_use_case import (
    GetFeedbackStatsUseCase,
)
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService

scenarios("unit/conversation/feedback_stats_cache.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _setup_stats_use_case(context, tenant_id, cache_ttl):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.count_by_tenant_and_rating = AsyncMock(return_value=10)

    cache_service = InMemoryCacheService()

    context["use_case"] = GetFeedbackStatsUseCase(
        feedback_repository=mock_repo,
        cache_service=cache_service,
        cache_ttl=cache_ttl,
    )
    context["mock_repo"] = mock_repo
    context["tenant_id"] = tenant_id


@given(parsers.parse('租戶 "{tenant_id}" 有回饋資料且快取 TTL 為 60 秒'))
def setup_with_long_ttl(context, tenant_id):
    _setup_stats_use_case(context, tenant_id, cache_ttl=60)


@given(parsers.parse('租戶 "{tenant_id}" 有回饋資料且快取 TTL 為 0 秒'))
def setup_with_zero_ttl(context, tenant_id):
    _setup_stats_use_case(context, tenant_id, cache_ttl=0)


@when("連續兩次查詢回饋統計")
def query_stats_twice(context):
    for _ in range(2):
        _run(context["use_case"].execute(context["tenant_id"]))


@then("Repository 的 count 方法應只被呼叫一輪")
def verify_single_round(context):
    # 一輪 = 2 次呼叫（total + thumbs_up）
    assert context["mock_repo"].count_by_tenant_and_rating.call_count == 2


@then("Repository 的 count 方法應被呼叫兩輪")
def verify_double_round(context):
    # 兩輪 = 4 次呼叫
    assert context["mock_repo"].count_by_tenant_and_rating.call_count == 4
