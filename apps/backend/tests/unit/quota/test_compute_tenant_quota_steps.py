"""ComputeTenantQuotaUseCase BDD Steps — S-Ledger-Unification P3"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.quota.compute_tenant_quota_use_case import (
    ComputeTenantQuotaUseCase,
    TenantQuotaSnapshot,
)

scenarios("unit/quota/compute_tenant_quota.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context() -> dict:
    return {"usage_by_category": {}, "topups": 0}


def _build_use_case(ctx: dict) -> ComputeTenantQuotaUseCase:
    """組出 use case，usage/topup repo 用 mock 從 ctx 狀態回值。"""
    tenant = SimpleNamespace(
        id=SimpleNamespace(value=ctx["tenant_id"]),
        plan="starter",
        included_categories=ctx["included_categories"],
    )
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=tenant)

    ledger = SimpleNamespace(
        cycle_year_month="2026-04",
        base_total=ctx["base_total"],
        plan_name="starter",
    )
    ensure_ledger = AsyncMock()
    ensure_ledger.execute = AsyncMock(return_value=ledger)

    usage_repo = AsyncMock()

    async def audit_sum(tenant_id, cycle):
        return sum(ctx["usage_by_category"].values())

    async def billable_sum(tenant_id, cycle, included):
        if included is None:
            return sum(ctx["usage_by_category"].values())
        if included == []:
            return 0
        return sum(
            v for c, v in ctx["usage_by_category"].items() if c in included
        )

    usage_repo.sum_tokens_in_cycle = AsyncMock(side_effect=audit_sum)
    usage_repo.sum_billable_tokens_in_cycle = AsyncMock(side_effect=billable_sum)

    topup_repo = AsyncMock()
    topup_repo.sum_amount_in_cycle = AsyncMock(
        side_effect=lambda t, c: ctx["topups"]
    )

    return ComputeTenantQuotaUseCase(
        tenant_repository=tenant_repo,
        ensure_ledger=ensure_ledger,
        usage_repository=usage_repo,
        topup_repository=topup_repo,
    )


@given(parsers.parse('已建立租戶 "{tenant}" 綁定 plan "{plan}" base_total={base:d}'))
def seed_tenant(context, tenant, plan, base):
    context["tenant_id"] = tenant
    context["plan"] = plan
    context["base_total"] = base
    context["included_categories"] = None  # default


@given('租戶 "acme" 的 included_categories 為 null')
def set_included_null(context):
    context["included_categories"] = None


@given(parsers.re(r'租戶 "acme" 的 included_categories 為 \[(?P<spec>.*)\]'))
def set_included_list(context, spec):
    if spec.strip() == "":
        context["included_categories"] = []
    else:
        parts = [p.strip().strip('"').strip("'") for p in spec.split(",")]
        context["included_categories"] = [p for p in parts if p]


@given(
    parsers.parse(
        '租戶 "acme" 本月寫入 usage {amount:d} tokens category "{category}"'
    )
)
def add_usage(context, amount, category):
    context["usage_by_category"][category] = (
        context["usage_by_category"].get(category, 0) + amount
    )


@given(parsers.parse('租戶 "acme" 已有 topup 紀錄 {amount:d}'))
def add_topup(context, amount):
    context["topups"] += amount


@when(
    '呼叫 ComputeTenantQuotaUseCase 查詢 "acme"', target_fixture="snapshot"
)
def compute_quota(context) -> TenantQuotaSnapshot:
    uc = _build_use_case(context)
    return _run(uc.execute(context["tenant_id"]))


@when(parsers.re(r'更新租戶 "acme" 的 included_categories 為 \[(?P<spec>.*)\]'))
def update_included(context, spec):
    if spec.strip() == "":
        context["included_categories"] = []
    else:
        parts = [p.strip().strip('"').strip("'") for p in spec.split(",")]
        context["included_categories"] = [p for p in parts if p]


@then(parsers.parse("total_audit_in_cycle 應等於 {expected:d}"))
def assert_audit(snapshot, expected):
    assert snapshot.total_audit_in_cycle == expected, (
        f"expected audit {expected}, got {snapshot.total_audit_in_cycle}"
    )


@then(parsers.parse("total_billable_in_cycle 應等於 {expected:d}"))
def assert_billable(snapshot, expected):
    assert snapshot.total_billable_in_cycle == expected, (
        f"expected billable {expected}, got {snapshot.total_billable_in_cycle}"
    )


@then(parsers.parse("base_remaining 應等於 {expected:d}"))
def assert_base_remaining(snapshot, expected):
    assert snapshot.base_remaining == expected, (
        f"expected base_remaining {expected}, got {snapshot.base_remaining}"
    )


@then(parsers.parse("addon_remaining 應等於 {expected:d}"))
def assert_addon_remaining(snapshot, expected):
    assert snapshot.addon_remaining == expected, (
        f"expected addon_remaining {expected}, got {snapshot.addon_remaining}"
    )


@then("base_total 減 base_remaining 應等於 total_billable_in_cycle")
def assert_drift_zero(snapshot):
    # 不變性核心：連 1 token 都不允許 drift
    # 僅在 billable ≤ base_total 時嚴格相等（否則差額進 overage）
    used = snapshot.base_total - snapshot.base_remaining
    assert used == min(snapshot.total_billable_in_cycle, snapshot.base_total), (
        f"base_total - base_remaining = {used}, "
        f"min(billable, base_total) = "
        f"{min(snapshot.total_billable_in_cycle, snapshot.base_total)}"
    )
