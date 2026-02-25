"""資料保留策略 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.data_retention_use_case import (
    DataRetentionUseCase,
)
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.shared.pii_masking import mask_pii_in_text

scenarios("unit/conversation/data_retention.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given(parsers.parse('租戶 "{tenant_id}" 有 {count:d} 筆超過 6 個月的回饋'))
def setup_old_feedback(context, tenant_id, count):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.delete_before_date = AsyncMock(return_value=count)
    context["use_case"] = DataRetentionUseCase(feedback_repository=mock_repo)
    context["tenant_id"] = tenant_id


@given(parsers.parse('租戶 "{tenant_id}" 無過期回饋'))
def setup_no_old_feedback(context, tenant_id):
    mock_repo = AsyncMock(spec=FeedbackRepository)
    mock_repo.delete_before_date = AsyncMock(return_value=0)
    context["use_case"] = DataRetentionUseCase(feedback_repository=mock_repo)
    context["tenant_id"] = tenant_id


@given("一段含有 email 和手機號碼的文字")
def setup_pii_text(context):
    context["text"] = "聯絡方式：user@example.com 手機 0912345678"


@when(parsers.parse("執行資料保留清理（{months:d} 個月）"))
def run_retention(context, months):
    context["result"] = _run(
        context["use_case"].execute(context["tenant_id"], months=months)
    )


@when("執行 PII 遮蔽")
def run_pii_mask(context):
    context["masked"] = mask_pii_in_text(context["text"])


@then(parsers.parse("應刪除 {count:d} 筆過期回饋"))
def verify_deleted_count(context, count):
    assert context["result"] == count


@then(parsers.parse("應刪除 {count:d} 筆"))
def verify_deleted_zero(context, count):
    assert context["result"] == count


@then("email 和手機應被替換為遮蔽字串")
def verify_pii_masked(context):
    masked = context["masked"]
    assert "user@example.com" not in masked
    assert "0912345678" not in masked
    assert "***" in masked
