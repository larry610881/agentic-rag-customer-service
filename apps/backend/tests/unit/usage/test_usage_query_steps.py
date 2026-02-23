"""Token 使用量查詢 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.usage.query_usage_use_case import QueryUsageUseCase
from src.domain.usage.value_objects import UsageSummary

scenarios("unit/usage/usage_query.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Scenario: 查詢租戶使用摘要 ---


@given('租戶 "tenant-001" 有 2 筆使用記錄')
def setup_2_records(context):
    mock_repo = AsyncMock()
    mock_repo.get_tenant_summary = AsyncMock(
        return_value=UsageSummary(
            tenant_id="tenant-001",
            total_input_tokens=300,
            total_output_tokens=150,
            total_tokens=450,
            total_cost=0.003,
            by_model={"fake": 200, "gpt-4o": 250},
            by_request_type={"rag": 200, "agent": 250},
        )
    )
    context["use_case"] = QueryUsageUseCase(usage_repository=mock_repo)
    context["mock_repo"] = mock_repo


@when('查詢租戶 "tenant-001" 的使用摘要')
def do_query_summary(context):
    context["summary"] = _run(
        context["use_case"].execute(tenant_id="tenant-001")
    )


@then("摘要應包含正確的 total_tokens")
def verify_total_tokens(context):
    assert context["summary"].total_tokens == 450


@then("摘要應包含 by_model 分類")
def verify_by_model(context):
    assert len(context["summary"].by_model) == 2
    assert "fake" in context["summary"].by_model
    assert "gpt-4o" in context["summary"].by_model


# --- Scenario: 按日期範圍查詢 ---


@given('租戶 "tenant-001" 有跨日期的使用記錄')
def setup_date_records(context):
    mock_repo = AsyncMock()
    mock_repo.get_tenant_summary = AsyncMock(
        return_value=UsageSummary(
            tenant_id="tenant-001",
            total_input_tokens=100,
            total_output_tokens=50,
            total_tokens=150,
            total_cost=0.001,
            by_model={"fake": 150},
            by_request_type={"rag": 150},
        )
    )
    context["use_case"] = QueryUsageUseCase(usage_repository=mock_repo)
    context["mock_repo"] = mock_repo


@when("查詢指定日期範圍的使用摘要")
def do_query_date_range(context):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, tzinfo=timezone.utc)
    context["summary"] = _run(
        context["use_case"].execute(
            tenant_id="tenant-001",
            start_date=start,
            end_date=end,
        )
    )
    context["start_date"] = start
    context["end_date"] = end


@then("只回傳範圍內的記錄摘要")
def verify_date_range(context):
    assert context["summary"].total_tokens == 150
    # Verify the repository was called with date params (positional or keyword)
    context["mock_repo"].get_tenant_summary.assert_called_once_with(
        "tenant-001", context["start_date"], context["end_date"]
    )
