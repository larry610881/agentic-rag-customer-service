"""分析查詢分頁 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.get_retrieval_quality_use_case import (
    GetRetrievalQualityUseCase,
)
from src.domain.conversation.feedback_analysis_vo import RetrievalQualityRecord
from src.domain.conversation.feedback_repository import FeedbackRepository

scenarios("unit/conversation/feedback_analysis_pagination.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_record(i: int) -> RetrievalQualityRecord:
    return RetrievalQualityRecord(
        user_question=f"問題 {i}",
        assistant_answer=f"回答 {i}",
        retrieved_chunks=[],
        rating="thumbs_down",
        comment=None,
        created_at=datetime.now(timezone.utc),
    )


@given(parsers.parse('租戶 "{tenant_id}" 有 {count:d} 筆差評資料'))
def setup_pagination_data(context, tenant_id, count):
    all_records = [_make_record(i) for i in range(count)]

    mock_repo = AsyncMock(spec=FeedbackRepository)

    def fake_get_negative(t, days=30, limit=20, offset=0):
        return all_records[offset : offset + limit]

    mock_repo.get_negative_with_context = AsyncMock(
        side_effect=fake_get_negative
    )
    mock_repo.count_negative = AsyncMock(return_value=count)

    context["use_case"] = GetRetrievalQualityUseCase(
        feedback_repository=mock_repo
    )
    context["tenant_id"] = tenant_id


@when(parsers.parse("查詢檢索品質分頁 offset {offset:d} limit {limit:d}"))
def query_with_pagination(context, offset, limit):
    context["result"] = _run(
        context["use_case"].execute(
            context["tenant_id"], days=30, limit=limit, offset=offset
        )
    )


@then(parsers.parse("應回傳 {count:d} 筆記錄與 total {total:d}"))
def verify_paginated_result(context, count, total):
    result = context["result"]
    assert len(result.records) == count
    assert result.total == total
