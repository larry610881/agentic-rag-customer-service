"""回饋分析 API BDD Step Definitions"""

import asyncio
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.get_retrieval_quality_use_case import (
    GetRetrievalQualityUseCase,
)
from src.application.conversation.get_satisfaction_trend_use_case import (
    GetSatisfactionTrendUseCase,
)
from src.application.conversation.get_token_cost_stats_use_case import (
    GetTokenCostStatsUseCase,
)
from src.application.conversation.get_top_issues_use_case import (
    GetTopIssuesUseCase,
)
from src.domain.conversation.feedback_analysis_vo import (
    DailyFeedbackStat,
    RetrievalQualityRecord,
    TagCount,
)
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import ModelCostStat

scenarios("unit/conversation/feedback_analysis.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given(parsers.parse('租戶 "{tenant_id}" 有 30 天內的回饋資料'))
def tenant_has_feedback_data(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.get_daily_trend = AsyncMock(
        return_value=[
            DailyFeedbackStat(
                date=date(2026, 2, 25),
                total=10,
                positive=7,
                negative=3,
                satisfaction_pct=70.0,
            ),
            DailyFeedbackStat(
                date=date(2026, 2, 26),
                total=5,
                positive=4,
                negative=1,
                satisfaction_pct=80.0,
            ),
        ]
    )
    context["mock_feedback_repo"] = mock_repo
    context["tenant_id"] = tenant_id
    context["trend_uc"] = GetSatisfactionTrendUseCase(
        feedback_repository=mock_repo
    )


@given(parsers.parse('租戶 "{tenant_id}" 有含 tags 的差評資料'))
def tenant_has_tagged_feedback(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.get_top_tags = AsyncMock(
        return_value=[
            TagCount(tag="incorrect", count=15),
            TagCount(tag="incomplete", count=8),
            TagCount(tag="irrelevant", count=3),
        ]
    )
    context["mock_feedback_repo"] = mock_repo
    context["tenant_id"] = tenant_id
    context["issues_uc"] = GetTopIssuesUseCase(feedback_repository=mock_repo)


@given(parsers.parse('租戶 "{tenant_id}" 有差評和對應的訊息上下文'))
def tenant_has_negative_context(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.get_negative_with_context = AsyncMock(
        return_value=[
            RetrievalQualityRecord(
                user_question="退貨政策是什麼？",
                assistant_answer="很抱歉無法回答",
                retrieved_chunks=[
                    {"document_name": "policy.md", "score": 0.3}
                ],
                rating="thumbs_down",
                comment="沒有回答我的問題",
                created_at=datetime.now(timezone.utc),
            )
        ]
    )
    mock_repo.count_negative = AsyncMock(return_value=1)
    context["mock_feedback_repo"] = mock_repo
    context["tenant_id"] = tenant_id
    context["quality_uc"] = GetRetrievalQualityUseCase(
        feedback_repository=mock_repo
    )


@given(parsers.parse('租戶 "{tenant_id}" 有使用記錄'))
def tenant_has_usage_records(context, tenant_id):
    mock_usage_repo = AsyncMock(spec=UsageRepository)
    mock_usage_repo.get_model_cost_stats = AsyncMock(
        return_value=[
            ModelCostStat(
                model="gpt-4o",
                message_count=100,
                input_tokens=50000,
                output_tokens=30000,
                avg_latency_ms=1200.0,
                estimated_cost=1.25,
            )
        ]
    )
    context["mock_usage_repo"] = mock_usage_repo
    context["tenant_id"] = tenant_id
    context["cost_uc"] = GetTokenCostStatsUseCase(
        usage_repository=mock_usage_repo
    )


@given(parsers.parse('租戶 "{tenant_id}" 無任何回饋資料'))
def tenant_has_no_data(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.get_daily_trend = AsyncMock(return_value=[])
    context["mock_feedback_repo"] = mock_repo
    context["tenant_id"] = tenant_id
    context["trend_uc"] = GetSatisfactionTrendUseCase(
        feedback_repository=mock_repo
    )


@when(parsers.parse("查詢滿意度趨勢（{days:d} 天）"))
def query_trend(context, days):
    context["result"] = _run(
        context["trend_uc"].execute(context["tenant_id"], days)
    )


@when(parsers.parse("查詢差評根因（{days:d} 天，top {limit:d}）"))
def query_issues(context, days, limit):
    context["result"] = _run(
        context["issues_uc"].execute(context["tenant_id"], days, limit)
    )


@when(parsers.parse("查詢檢索品質（{days:d} 天）"))
def query_quality(context, days):
    context["result"] = _run(
        context["quality_uc"].execute(context["tenant_id"], days)
    )


@when(parsers.parse("查詢 Token 成本統計（{days:d} 天）"))
def query_cost(context, days):
    context["result"] = _run(
        context["cost_uc"].execute(context["tenant_id"], days)
    )


@then("應回傳每日統計列表含 positive 和 negative")
def verify_trend_stats(context):
    result = context["result"]
    assert len(result) >= 1
    assert hasattr(result[0], "positive")
    assert hasattr(result[0], "negative")
    assert result[0].total > 0


@then("應回傳 tag 計數列表且依 count 降序")
def verify_top_issues(context):
    result = context["result"]
    assert len(result) >= 2
    assert result[0].count >= result[1].count
    assert result[0].tag == "incorrect"


@then("應回傳包含使用者問題和助理回答的記錄")
def verify_retrieval_quality(context):
    result = context["result"]
    assert result.total >= 1
    assert len(result.records) >= 1
    assert result.records[0].user_question != ""
    assert result.records[0].assistant_answer != ""
    assert isinstance(result.records[0].retrieved_chunks, list)


@then("應回傳每模型的 token 和成本摘要")
def verify_token_cost(context):
    result = context["result"]
    assert len(result) >= 1
    assert result[0].model == "gpt-4o"
    assert result[0].input_tokens > 0
    assert result[0].estimated_cost > 0


@then("應回傳空列表")
def verify_empty_list(context):
    assert context["result"] == []
