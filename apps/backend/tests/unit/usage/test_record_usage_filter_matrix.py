"""錢相關精確 filter matrix — 驗證每個 UsageCategory 的 in/out list 行為。

任何 silent deduction drop = 錢算錯；任何 over-deduction = 客戶被多扣。
本測試不容忍模糊：每個 category 的 enabled / disabled 路徑各一條斷言。

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #35
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.rag.value_objects import TokenUsage
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId
from src.domain.usage.category import UsageCategory

ALL_CATEGORIES = sorted(c.value for c in UsageCategory)

# Stage 4.1 刪除 OTHER 後 → 12 個。
# S-Gov.6b 加 conversation_summary → 13 個。
EXPECTED_CATEGORIES: set[str] = {
    "rag",
    "chat_web",
    "chat_widget",
    "chat_line",
    "ocr",
    "embedding",
    "guard",
    "rerank",
    "contextual_retrieval",
    "pdf_rename",
    "auto_classification",
    "intent_classify",
    "conversation_summary",  # S-Gov.6b
}

FIXED_TOKENS = 12345  # 明確 odd 數，避免意外等於預設 0 導致假陽性


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_tenant(included: list[str] | None) -> Tenant:
    return Tenant(
        id=TenantId(value="test-tenant"),
        name="Test",
        plan="starter",
        included_categories=included,
    )


def _make_usage(model: str = "gpt-4o") -> TokenUsage:
    half = FIXED_TOKENS // 2
    return TokenUsage(
        model=model,
        input_tokens=half,
        output_tokens=FIXED_TOKENS - half,
        total_tokens=FIXED_TOKENS,
    )


def _make_use_case(tenant: Tenant | None, deduct: AsyncMock | None = None):
    usage_repo = AsyncMock()
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=tenant)
    deduct = deduct or AsyncMock()
    uc = RecordUsageUseCase(
        usage_repository=usage_repo,
        deduct_tokens=deduct,
        tenant_repository=tenant_repo,
    )
    return uc, usage_repo, deduct, tenant_repo


# ---------------------------------------------------------------------------
# Case A — category 在 included_categories 內 → 必須扣，且 tokens 精確
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_deducts_when_category_explicitly_included(category):
    tenant = _make_tenant(included=[category])
    uc, usage_repo, deduct, _ = _make_use_case(tenant)

    _run(uc.execute(
        tenant_id="test-tenant",
        request_type=category,
        usage=_make_usage(),
    ))

    usage_repo.save.assert_awaited_once()
    deduct.execute.assert_awaited_once()
    call_kwargs = deduct.execute.await_args.kwargs
    assert call_kwargs["tokens"] == FIXED_TOKENS
    assert call_kwargs["tenant_id"] == "test-tenant"
    assert call_kwargs["plan_name"] == "starter"


# ---------------------------------------------------------------------------
# Case B — category 不在 included_categories 內 → 絕不扣，但 audit 永遠寫
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_skips_deduct_when_category_not_in_list(category):
    others = [c for c in ALL_CATEGORIES if c != category]
    tenant = _make_tenant(included=others)
    uc, usage_repo, deduct, _ = _make_use_case(tenant)

    _run(uc.execute(
        tenant_id="test-tenant",
        request_type=category,
        usage=_make_usage(),
    ))

    usage_repo.save.assert_awaited_once()      # audit 永遠寫
    deduct.execute.assert_not_awaited()        # 絕不扣


# ---------------------------------------------------------------------------
# Case C — included_categories = None → 每個 category 都扣（safe default）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_deducts_all_when_included_is_none(category):
    tenant = _make_tenant(included=None)
    uc, _usage_repo, deduct, _ = _make_use_case(tenant)

    _run(uc.execute(
        tenant_id="test-tenant",
        request_type=category,
        usage=_make_usage(),
    ))

    deduct.execute.assert_awaited_once()
    assert deduct.execute.await_args.kwargs["tokens"] == FIXED_TOKENS


# ---------------------------------------------------------------------------
# Case D — included_categories = [] → 每個 category 都不扣（POC 免計費）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_skips_all_when_included_is_empty(category):
    tenant = _make_tenant(included=[])
    uc, usage_repo, deduct, _ = _make_use_case(tenant)

    _run(uc.execute(
        tenant_id="test-tenant",
        request_type=category,
        usage=_make_usage(),
    ))

    usage_repo.save.assert_awaited_once()
    deduct.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# Case E — enum fence：UsageCategory 必須剛好是 EXPECTED_CATEGORIES
# ---------------------------------------------------------------------------
def test_enum_coverage_fence():
    """若有人新增 / 刪除 UsageCategory 成員，CI 黃燈提醒同步更新。

    Stage 4.1 刪除 OTHER 後 actual == EXPECTED_CATEGORIES。
    在 OTHER 還在時（Stage 4 之前），此測試應 FAIL（紅燈）。
    """
    actual = {c.value for c in UsageCategory}
    assert actual == EXPECTED_CATEGORIES, (
        f"UsageCategory 不符預期 12 個；"
        f"差異={actual.symmetric_difference(EXPECTED_CATEGORIES)}"
    )


# ---------------------------------------------------------------------------
# Case F — deduction 丟例外不可污染 usage_record（既有 try/except 安全網驗證）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_deduct_failure_does_not_break_audit(category, monkeypatch):
    """錢丟了要至少留下 warning log，但絕不該 raise 污染 audit。

    Patch src.application.usage.record_usage_use_case.logger 作 spy，
    比 caplog 可靠（structlog 經 stdlib bridge 後的行為不一致）。
    """
    from src.application.usage import record_usage_use_case as ruu

    warning_calls = []
    fake_logger = type("L", (), {
        "warning": lambda self, *a, **kw: warning_calls.append((a, kw)),
        "info": lambda self, *a, **kw: None,
        "debug": lambda self, *a, **kw: None,
        "error": lambda self, *a, **kw: None,
    })()
    monkeypatch.setattr(ruu, "logger", fake_logger)

    tenant = _make_tenant(included=[category])
    deduct = AsyncMock()
    deduct.execute = AsyncMock(side_effect=RuntimeError("simulated ledger outage"))
    uc, usage_repo, _, _ = _make_use_case(tenant, deduct=deduct)

    # 不應 raise（audit 優先於計費）
    _run(uc.execute(
        tenant_id="test-tenant",
        request_type=category,
        usage=_make_usage(),
    ))

    # audit 仍然完整
    usage_repo.save.assert_awaited_once()
    # 至少一次 warning 呼叫 — 錢丟了不能靜默
    assert len(warning_calls) >= 1, "deduction 失敗應至少留一筆 warning log"
    # warning event 名稱應含 deduct_failed（方便 alerting grep）
    first_args = warning_calls[0][0]
    event = first_args[0] if first_args else ""
    assert "deduct_failed" in event


# ---------------------------------------------------------------------------
# Case G — 白名單：非 enum 字串必須拒絕（防 legacy / typo）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_value", ["other", "agent", "unknown", "", "CHAT_WEB"])
def test_rejects_non_enum_request_type(bad_value):
    tenant = _make_tenant(included=None)
    uc, usage_repo, deduct, _ = _make_use_case(tenant)

    with pytest.raises(ValueError):
        _run(uc.execute(
            tenant_id="test-tenant",
            request_type=bad_value,
            usage=_make_usage(),
        ))
    usage_repo.save.assert_not_called()
    deduct.execute.assert_not_called()
