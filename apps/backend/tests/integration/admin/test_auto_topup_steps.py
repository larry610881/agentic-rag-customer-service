"""Auto-topup + Quota Alerts — BDD Step Definitions (S-Token-Gov.3)

驗證 RecordUsageUseCase 的 auto-topup hook 在 base 與 addon 皆耗盡時觸發
TopupAddonUseCase（ea7cbb3 起取代已刪除的 DeductTokensUseCase），
以及 ProcessQuotaAlertsUseCase 寫 80%/100% 警示且重跑冪等。
"""

from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.billing.quota_alert import (
    ALERT_TYPE_BASE_EXHAUSTED_100,
    ALERT_TYPE_BASE_WARNING_80,
)
from src.domain.ledger.entity import current_year_month
from src.domain.ledger.topup_entity import REASON_MANUAL_ADJUST, TokenLedgerTopup
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.entity import UsageRecord

scenarios("integration/admin/auto_topup.feature")


SEED_PLANS = [
    {
        "name": "poc",
        "base_monthly_tokens": 10_000_000,
        "addon_pack_tokens": 5_000_000,
        "base_price": 0,
        "addon_price": 0,
        "currency": "TWD",
        "description": "POC test",
    },
    {
        "name": "starter",
        "base_monthly_tokens": 10_000_000,
        "addon_pack_tokens": 5_000_000,
        "base_price": 3000,
        "addon_price": 1500,
        "currency": "TWD",
        "description": "starter",
    },
    {
        "name": "pro",
        "base_monthly_tokens": 30_000_000,
        "addon_pack_tokens": 15_000_000,
        "base_price": 8000,
        "addon_price": 3500,
        "currency": "TWD",
        "description": "pro",
    },
]


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("admin 已登入並 seed 三個方案")
def admin_logged_in_and_seed(ctx, client, admin_headers):
    ctx["admin_headers"] = admin_headers
    ctx["tenants"] = {}
    for plan_data in SEED_PLANS:
        resp = client.post(
            "/api/v1/admin/plans", json=plan_data, headers=admin_headers
        )
        if resp.status_code not in (201, 409):
            raise AssertionError(f"plan seed failed: {resp.text}")


@given(parsers.parse('已建立租戶 "{tname}" 綁定 plan "{plan_name}"'))
def create_tenant_with_plan(ctx, client, app, tname, plan_name):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": tname},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    ctx["tenants"][tname] = tenant_id
    ctx["app"] = app

    assign = client.post(
        f"/api/v1/admin/plans/{plan_name}/assign/{tenant_id}",
        headers=ctx["admin_headers"],
    )
    assert assign.status_code == 204, assign.text


@given(parsers.parse(
    '已建立 plan "{plan_name}" 其 addon_pack_tokens={pack:d}'
))
def create_custom_plan(ctx, client, plan_name, pack):
    resp = client.post(
        "/api/v1/admin/plans",
        json={
            "name": plan_name,
            "base_monthly_tokens": 10_000_000,
            "addon_pack_tokens": pack,
            "base_price": 0,
            "addon_price": 0,
            "currency": "TWD",
            "description": f"{plan_name} test plan",
        },
        headers=ctx["admin_headers"],
    )
    assert resp.status_code in (201, 409), resp.text


# ---------------------------------------------------------------------------
# Ledger 預設狀態 — 沿用 token_ledger_steps 的 setup pattern
# ---------------------------------------------------------------------------


@given(parsers.parse(
    "{tname} 本月 ledger base_remaining={base:d} addon_remaining={addon:d}"
))
def setup_ledger_with_state(ctx, tname, base, addon):
    """以 SSOT 資料造出指定餘額。

    ea7cbb3（S-Ledger-Unification）後 base/addon_remaining 由
    ComputeTenantQuotaUseCase 從 SUM(usage) + SUM(topups) 即時算出，
    改 ledger 欄位不再有任何效果（ProcessQuotaAlerts 也讀 compute_quota）。
    故以「補差額」方式造狀態，可重複呼叫（同 scenario 內第二次 Given）：

    - 直接寫 usage record（繞過 record_usage 的 auto-topup hook）讓
      billable = base_total - base
    - 寫 manual_adjust topup（可為負 = 手動扣）讓 addon_remaining = addon
    """
    container = ctx["app"].container
    tenant_id = ctx["tenants"][tname]
    ctx["current_tenant"] = tname

    async def _setup():
        tenant = await container.tenant_repository().find_by_id(tenant_id)
        assert tenant is not None
        await container.ensure_ledger_use_case().execute(tenant_id, tenant.plan)
        compute = container.compute_tenant_quota_use_case()
        snap = await compute.execute(tenant_id)
        delta_usage = (snap.base_total - base) - snap.total_billable_in_cycle
        assert delta_usage >= 0, "無法以追加 usage 回到較高 base_remaining"
        if delta_usage:
            await container.usage_repository().save(
                UsageRecord(
                    tenant_id=tenant_id,
                    request_type="chat_web",
                    model="test",
                    input_tokens=delta_usage,
                )
            )
            snap = await compute.execute(tenant_id)
        delta_topup = addon - snap.addon_remaining
        if delta_topup:
            await container.token_ledger_topup_repository().save(
                TokenLedgerTopup(
                    tenant_id=tenant_id,
                    cycle_year_month=snap.cycle_year_month,
                    amount=delta_topup,
                    reason=REASON_MANUAL_ADJUST,
                )
            )

    _run(_setup())


# ---------------------------------------------------------------------------
# When: record_usage / cron
# ---------------------------------------------------------------------------


@when(parsers.parse("record_usage 寫入 {n:d} tokens 給 {tname}"))
def record_usage(ctx, n, tname):
    container = ctx["app"].container
    record_usage = container.record_usage_use_case()
    tenant_id = ctx["tenants"][tname]
    ctx["current_tenant"] = tname
    _run(
        record_usage.execute(
            tenant_id=tenant_id,
            request_type="chat_web",  # Issue #73：rag 已 deprecated（僅供讀取）
            usage=TokenUsage(
                model="test",
                input_tokens=n,
                output_tokens=0,
                # total_tokens 已改 @property（fbeeec6）
            ),
        )
    )


@when("執行 ProcessQuotaAlertsUseCase")
def run_process_quota_alerts(ctx):
    container = ctx["app"].container
    use_case = container.process_quota_alerts_use_case()
    ctx["alerts_stats"] = _run(use_case.execute())


@when("再執行一次 ProcessQuotaAlertsUseCase")
def run_process_quota_alerts_again(ctx):
    container = ctx["app"].container
    use_case = container.process_quota_alerts_use_case()
    ctx["alerts_stats_2"] = _run(use_case.execute())


# ---------------------------------------------------------------------------
# Then: 驗證 ledger / billing transaction / alert log
# ---------------------------------------------------------------------------


@then(parsers.parse("addon_remaining 應為 {n:d}"))
def verify_addon_remaining(ctx, n):
    container = ctx["app"].container
    # 預設驗第一個 tenant — 但若 ctx 有設 current_tenant 用那個
    tenant_name = ctx.get("current_tenant") or list(ctx["tenants"].keys())[0]
    tenant_id = ctx["tenants"][tenant_name]
    # ea7cbb3：addon_remaining 唯一讀取入口為 ComputeTenantQuotaUseCase
    compute = container.compute_tenant_quota_use_case()
    quota = _run(compute.execute(tenant_id))
    assert quota.addon_remaining == n, (
        f"addon_remaining: expected {n}, got {quota.addon_remaining}"
    )


@then(parsers.parse("該租戶本月應有 {n:d} 筆 BillingTransaction"))
def verify_billing_count(ctx, n):
    container = ctx["app"].container
    billing_repo = container.billing_transaction_repository()
    cycle = current_year_month()
    tenant_name = ctx.get("current_tenant") or list(ctx["tenants"].keys())[0]
    tenant_id = ctx["tenants"][tenant_name]
    txs = _run(
        billing_repo.find_by_tenant_and_cycle(tenant_id, cycle)
    )
    assert len(txs) == n, (
        f"expected {n} transactions, got {len(txs)}: "
        f"{[t.transaction_type for t in txs]}"
    )
    ctx["billing_txs"] = txs


@then(parsers.parse('最新 BillingTransaction.transaction_type 應為 "{ttype}"'))
def verify_latest_tx_type(ctx, ttype):
    txs = ctx["billing_txs"]
    assert len(txs) > 0
    assert txs[-1].transaction_type == ttype


@then(parsers.parse("最新 BillingTransaction.addon_tokens_added 應為 {n:d}"))
def verify_latest_tx_addon(ctx, n):
    txs = ctx["billing_txs"]
    assert len(txs) > 0
    assert txs[-1].addon_tokens_added == n


@then(parsers.parse("{tname} 應有 {n:d} 筆 base_warning_80 警示"))
def verify_warning_count(ctx, tname, n):
    container = ctx["app"].container
    alert_repo = container.quota_alert_log_repository()
    tenant_id = ctx["tenants"][tname]
    cycle = current_year_month()
    alerts = _run(alert_repo.find_by_tenant_and_cycle(tenant_id, cycle))
    matching = [a for a in alerts if a.alert_type == ALERT_TYPE_BASE_WARNING_80]
    assert len(matching) == n, (
        f"{tname}.warning_80 count expected {n}, got {len(matching)}: "
        f"all_alerts={[a.alert_type for a in alerts]}"
    )


@then(parsers.parse("{tname} 應有 {n:d} 筆 base_exhausted_100 警示"))
def verify_exhausted_count(ctx, tname, n):
    container = ctx["app"].container
    alert_repo = container.quota_alert_log_repository()
    tenant_id = ctx["tenants"][tname]
    cycle = current_year_month()
    alerts = _run(alert_repo.find_by_tenant_and_cycle(tenant_id, cycle))
    matching = [
        a for a in alerts if a.alert_type == ALERT_TYPE_BASE_EXHAUSTED_100
    ]
    assert len(matching) == n, (
        f"{tname}.exhausted_100 count expected {n}, got {len(matching)}"
    )
