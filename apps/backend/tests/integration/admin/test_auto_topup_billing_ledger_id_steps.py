"""auto_topup BillingTransaction.ledger_id 指向真實 ledger (T1.1) BDD Steps.

驗證 P4 regression bug 修復後，auto_topup 寫入 BillingTransaction 不會因 FK
violation 靜默失敗，金流審計紀錄正確可追蹤。
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.ledger.entity import current_year_month
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.entity import UsageRecord

scenarios("integration/admin/auto_topup_billing_ledger_id.feature")


SEED_PLANS = [
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
    {
        "name": "poc",
        "base_monthly_tokens": 10_000_000,
        "addon_pack_tokens": 5_000_000,
        "base_price": 0,
        "addon_price": 0,
        "currency": "TWD",
        "description": "poc",
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
def admin_seed_plans(ctx, client, admin_headers):
    ctx["admin_headers"] = admin_headers
    ctx["tenants"] = {}
    for plan_data in SEED_PLANS:
        resp = client.post(
            "/api/v1/admin/plans", json=plan_data, headers=admin_headers
        )
        if resp.status_code not in (201, 409):
            raise AssertionError(f"plan seed failed: {resp.text}")


@given(parsers.parse('已建立租戶 "{tname}" 綁定 plan "{plan_name}"'))
def create_tenant(ctx, client, app, tname, plan_name):
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


# ---------------------------------------------------------------------------
# Given: seed state via new primitives (usage_records writes)
# ---------------------------------------------------------------------------


@given(parsers.parse("{tname} 本月 base 和 addon 都已耗盡"))
def seed_exhausted_state(ctx, tname):
    """寫 usage_records 到 base_total 全耗盡。無 topup → addon_remaining=0。
    這樣 base + addon 同時耗盡 → 下一筆 record_usage 會 trigger auto_topup。"""
    container = ctx["app"].container
    usage_repo = container.usage_repository()
    ensure = container.ensure_ledger_use_case()
    tenant_repo = container.tenant_repository()
    tenant_id = ctx["tenants"][tname]
    ctx["current_tenant"] = tname

    tenant = _run(tenant_repo.find_by_id(tenant_id))
    assert tenant is not None
    ledger = _run(ensure.execute(tenant_id, tenant.plan))

    # 一次寫一筆 category="rag" 的 usage 吃掉全 base
    _run(usage_repo.save(UsageRecord(
        id=str(uuid4()),
        tenant_id=tenant_id,
        request_type="rag",
        model="test",
        input_tokens=ledger.base_total,
        output_tokens=0,
        estimated_cost=0.0,
    )))


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse("record_usage 寫入 {n:d} tokens 給 {tname}"))
def record_usage_step(ctx, n, tname):
    container = ctx["app"].container
    uc = container.record_usage_use_case()
    tenant_id = ctx["tenants"][tname]
    ctx["current_tenant"] = tname
    _run(uc.execute(
        tenant_id=tenant_id,
        request_type="rag",
        usage=TokenUsage(
            model="test",
            input_tokens=n,
            output_tokens=0,
        ),
    ))


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("{tname} 本月應有 {n:d} 筆 BillingTransaction"))
def verify_billing_count(ctx, tname, n):
    container = ctx["app"].container
    billing_repo = container.billing_transaction_repository()
    cycle = current_year_month()
    tenant_id = ctx["tenants"][tname]
    txs = _run(billing_repo.find_by_tenant_and_cycle(tenant_id, cycle))
    assert len(txs) == n, (
        f"{tname} expected {n} BillingTransactions, got {len(txs)}: "
        f"{[(t.transaction_type, t.ledger_id) for t in txs]}"
    )
    ctx["billing_txs"] = txs


@then(parsers.parse("最新 BillingTransaction.ledger_id 應等於 {tname} 本月 ledger.id"))
def verify_ledger_id_matches(ctx, tname):
    txs = ctx["billing_txs"]
    assert len(txs) > 0
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    cycle = current_year_month()
    tenant_id = ctx["tenants"][tname]
    ledger = _run(ledger_repo.find_by_tenant_and_cycle(tenant_id, cycle))
    assert ledger is not None
    assert txs[-1].ledger_id == ledger.id, (
        f"expected ledger_id={ledger.id}, got {txs[-1].ledger_id!r}"
    )


@then("最新 BillingTransaction.ledger_id 不應為空字串")
def verify_ledger_id_non_empty(ctx):
    txs = ctx["billing_txs"]
    assert len(txs) > 0
    assert txs[-1].ledger_id != "", (
        f"BillingTransaction.ledger_id is empty string — FK regression!"
    )
    assert txs[-1].ledger_id is not None
