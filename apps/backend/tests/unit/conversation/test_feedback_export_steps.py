"""回饋匯出 BDD Step Definitions"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.export_feedback_use_case import (
    ExportFeedbackUseCase,
)
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)

scenarios("unit/conversation/feedback_export.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_feedbacks(user_id="user-001"):
    return [
        Feedback(
            id=FeedbackId(value="fb-001"),
            tenant_id="t-001",
            conversation_id="conv-001",
            message_id="msg-001",
            user_id=user_id,
            channel=Channel.WEB,
            rating=Rating.THUMBS_UP,
            comment="很好",
            tags=["helpful"],
            created_at=datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc),
        ),
    ]


@given(parsers.parse('租戶 "{tenant_id}" 有可匯出的回饋資料'))
def setup_exportable_feedback(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.find_by_date_range = AsyncMock(return_value=_make_feedbacks())
    context["use_case"] = ExportFeedbackUseCase(feedback_repository=mock_repo)
    context["tenant_id"] = tenant_id


@given(parsers.parse('租戶 "{tenant_id}" 有含 PII 的回饋資料'))
def setup_pii_feedback(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.find_by_date_range = AsyncMock(
        return_value=_make_feedbacks(user_id="U1234567890abcdef1234567890abcdef")
    )
    context["use_case"] = ExportFeedbackUseCase(feedback_repository=mock_repo)
    context["tenant_id"] = tenant_id


@given(parsers.parse('租戶 "{tenant_id}" 無回饋資料'))
def setup_no_feedback(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.find_by_date_range = AsyncMock(return_value=[])
    context["use_case"] = ExportFeedbackUseCase(feedback_repository=mock_repo)
    context["tenant_id"] = tenant_id


@when("以 JSON 格式匯出（不遮蔽 PII）")
def export_json(context):
    context["result"] = _run(
        context["use_case"].execute(
            context["tenant_id"], format="json", mask_pii=False
        )
    )


@when("以 CSV 格式匯出（不遮蔽 PII）")
def export_csv(context):
    context["result"] = _run(
        context["use_case"].execute(
            context["tenant_id"], format="csv", mask_pii=False
        )
    )


@when("以 JSON 格式匯出（啟用 PII 遮蔽）")
def export_json_masked(context):
    context["result"] = _run(
        context["use_case"].execute(
            context["tenant_id"], format="json", mask_pii=True
        )
    )


@then("回傳內容應為合法 JSON 且包含回饋記錄")
def verify_json_content(context):
    data = json.loads(context["result"])
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "rating" in data[0]
    assert "message_id" in data[0]


@then("回傳內容應為合法 CSV 含標題列")
def verify_csv_content(context):
    lines = context["result"].strip().split("\n")
    assert len(lines) >= 2  # header + data
    assert "rating" in lines[0]
    assert "message_id" in lines[0]


@then("user_id 應被遮蔽")
def verify_pii_masked(context):
    data = json.loads(context["result"])
    assert len(data) >= 1
    uid = data[0]["user_id"]
    assert "***" in uid


@then("回傳空 JSON 陣列")
def verify_empty_json(context):
    data = json.loads(context["result"])
    assert data == []
