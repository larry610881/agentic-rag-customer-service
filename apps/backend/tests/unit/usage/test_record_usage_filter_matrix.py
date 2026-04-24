"""RecordUsageUseCase 行為 matrix — S-Ledger-Unification P5 rewrite

舊版本測試「category filter 決定 deduct 是否觸發」— 但 P4 後 deduct 不復存在：
- Record 無條件寫 usage_records（審計永遠不變）
- billable filter 改由 ComputeTenantQuotaUseCase 讀取時套用（retroactive）
- auto-topup 由 RecordUsageUseCase 寫入後檢查 compute_quota 觸發

本檔聚焦驗證 RecordUsageUseCase 的新職責：
- Case A: 永遠寫 usage_records（不分 category）
- Case B: 非 enum category 拒絕
- Case C: compute_quota 說 base+addon 耗盡 → 呼叫 topup_addon
- Case D: compute_quota 有餘額 → 不呼叫 topup_addon
- Case E: compute_quota / topup_addon 例外不污染 audit（warn log 保留）
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.rag.value_objects import TokenUsage
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId
from src.domain.usage.category import UsageCategory

ALL_CATEGORIES = sorted(c.value for c in UsageCategory)

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
    "conversation_summary",
}

FIXED_TOKENS = 12345


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
    )


def _make_use_case(
    tenant: Tenant | None,
    *,
    base_remaining: int = 10_000_000,
    addon_remaining: int = 0,
    topup_mock: AsyncMock | None = None,
    compute_mock: AsyncMock | None = None,
):
    usage_repo = AsyncMock()
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=tenant)

    snapshot = SimpleNamespace(
        cycle_year_month="2026-04",
        base_remaining=base_remaining,
        addon_remaining=addon_remaining,
    )
    compute = compute_mock or AsyncMock()
    if compute_mock is None:
        compute.execute = AsyncMock(return_value=snapshot)

    topup = topup_mock or AsyncMock()
    plan_repo = AsyncMock()
    plan = SimpleNamespace(
        name="starter", addon_pack_tokens=5_000_000, currency="TWD"
    )
    plan_repo.find_by_name = AsyncMock(return_value=plan)

    uc = RecordUsageUseCase(
        usage_repository=usage_repo,
        compute_quota=compute,
        topup_addon=topup,
        tenant_repository=tenant_repo,
        plan_repository=plan_repo,
    )
    return uc, usage_repo, compute, topup


# --------------------------------------------------------------------------
# Case A — audit 永遠寫（不分 category, 不分 filter）
# --------------------------------------------------------------------------
@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_usage_record_saved_regardless_of_category(category):
    tenant = _make_tenant(included=[category])  # 有 filter
    uc, usage_repo, _, _ = _make_use_case(tenant)
    _run(uc.execute(
        tenant_id="test-tenant",
        request_type=category,
        usage=_make_usage(),
    ))
    usage_repo.save.assert_awaited_once()


@pytest.mark.parametrize("category", ALL_CATEGORIES)
def test_usage_record_saved_when_category_excluded(category):
    """即使 category 被 include list 排除，usage_records 仍寫（審計不漏）。"""
    tenant = _make_tenant(included=[])  # 全部不計入
    uc, usage_repo, _, _ = _make_use_case(tenant)
    _run(uc.execute(
        tenant_id="test-tenant",
        request_type=category,
        usage=_make_usage(),
    ))
    usage_repo.save.assert_awaited_once()


# --------------------------------------------------------------------------
# Case B — enum fence + 非 enum 拒絕
# --------------------------------------------------------------------------
def test_enum_coverage_fence():
    actual = {c.value for c in UsageCategory}
    assert actual == EXPECTED_CATEGORIES, (
        f"UsageCategory 不符預期；差異="
        f"{actual.symmetric_difference(EXPECTED_CATEGORIES)}"
    )


@pytest.mark.parametrize("bad_value", ["other", "agent", "unknown", "", "CHAT_WEB"])
def test_rejects_non_enum_request_type(bad_value):
    tenant = _make_tenant(included=None)
    uc, usage_repo, _, topup = _make_use_case(tenant)
    with pytest.raises(ValueError):
        _run(uc.execute(
            tenant_id="test-tenant",
            request_type=bad_value,
            usage=_make_usage(),
        ))
    usage_repo.save.assert_not_called()
    topup.execute.assert_not_called()


# --------------------------------------------------------------------------
# Case C — base+addon 都耗盡 → 觸發 auto-topup
# --------------------------------------------------------------------------
def test_triggers_topup_when_base_and_addon_exhausted():
    tenant = _make_tenant(included=None)
    uc, _, _, topup = _make_use_case(
        tenant, base_remaining=0, addon_remaining=-100
    )
    _run(uc.execute(
        tenant_id="test-tenant",
        request_type="rag",
        usage=_make_usage(),
    ))
    topup.execute.assert_awaited_once()
    kwargs = topup.execute.await_args.kwargs
    assert kwargs["tenant_id"] == "test-tenant"
    assert kwargs["cycle_year_month"] == "2026-04"


# --------------------------------------------------------------------------
# Case D — base 還有餘額 → 不觸發
# --------------------------------------------------------------------------
def test_does_not_trigger_topup_when_base_has_balance():
    tenant = _make_tenant(included=None)
    uc, _, _, topup = _make_use_case(
        tenant, base_remaining=5_000_000, addon_remaining=0
    )
    _run(uc.execute(
        tenant_id="test-tenant",
        request_type="rag",
        usage=_make_usage(),
    ))
    topup.execute.assert_not_called()


def test_does_not_trigger_topup_when_addon_still_positive():
    tenant = _make_tenant(included=None)
    uc, _, _, topup = _make_use_case(
        tenant, base_remaining=0, addon_remaining=1_000_000
    )
    _run(uc.execute(
        tenant_id="test-tenant",
        request_type="rag",
        usage=_make_usage(),
    ))
    topup.execute.assert_not_called()


# --------------------------------------------------------------------------
# Case E — compute_quota / topup 例外不污染 audit
# --------------------------------------------------------------------------
def test_topup_hook_failure_does_not_break_audit(monkeypatch):
    from src.application.usage import record_usage_use_case as ruu

    warning_calls = []
    fake_logger = type("L", (), {
        "warning": lambda self, *a, **kw: warning_calls.append((a, kw)),
        "info": lambda self, *a, **kw: None,
        "debug": lambda self, *a, **kw: None,
        "error": lambda self, *a, **kw: None,
    })()
    monkeypatch.setattr(ruu, "logger", fake_logger)

    tenant = _make_tenant(included=None)
    topup = AsyncMock()
    topup.execute = AsyncMock(side_effect=RuntimeError("topup outage"))
    uc, usage_repo, _, _ = _make_use_case(
        tenant, base_remaining=0, addon_remaining=0, topup_mock=topup
    )

    _run(uc.execute(
        tenant_id="test-tenant",
        request_type="rag",
        usage=_make_usage(),
    ))

    usage_repo.save.assert_awaited_once()
    assert len(warning_calls) >= 1
    event = warning_calls[0][0][0] if warning_calls[0][0] else ""
    assert "auto_topup" in event
