"""Billing Dashboard — BDD Step Definitions (S-Token-Gov.4)

驗證 GET /api/v1/admin/billing/dashboard 回傳 monthly_revenue / by_plan /
top_tenants 三個聚合，按 cycle range 正確過濾，非 admin 拒絕。
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.billing.entity import (
    TRANSACTION_TYPE_AUTO_TOPUP,
    TRIGGERED_BY_SYSTEM,
    BillingTransaction,
)
from src.domain.ledger.entity import current_year_month

scenarios("integration/admin/billing_dashboard.feature")


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


# ---------------------------------------------------------------------------
# Given: Seed BillingTransaction（直接寫 DB，模擬 .3 auto-topup 已發生過）
# ---------------------------------------------------------------------------


@given(parsers.parse(
    '{tname} 在 cycle "{cycle}" 有 {n:d} 筆 auto_topup '
    '金額 {amount:d} TWD addon {tokens:d}'
))
def seed_billing_transactions(ctx, tname, cycle, n, amount, tokens):
    """單一 _run() 內完成 ensure_ledger + n 個 BillingTransaction 寫入。

    一定要在同一 event loop 跑完所有 DB 操作，否則 asyncpg connection
    跨 loop 會炸 'got Future attached to a different loop'。
    """
    from datetime import datetime, timezone
    from uuid import uuid4

    from src.domain.ledger.entity import TokenLedger

    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    tenant_repo = container.tenant_repository()
    billing_repo = container.billing_transaction_repository()
    tenant_id = ctx["tenants"][tname]

    async def _seed():
        tenant = await tenant_repo.find_by_id(tenant_id)
        assert tenant is not None
        plan_name = tenant.plan

        ledger = await ledger_repo.find_by_tenant_and_cycle(tenant_id, cycle)
        if ledger is None:
            ledger = TokenLedger(
                id=str(uuid4()),
                tenant_id=tenant_id,
                cycle_year_month=cycle,
                plan_name=plan_name,
                base_total=10_000_000,
                base_remaining=10_000_000,
                addon_remaining=0,
                total_used_in_cycle=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            await ledger_repo.save(ledger)

        for _ in range(n):
            tx = BillingTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                cycle_year_month=cycle,
                plan_name=plan_name,
                transaction_type=TRANSACTION_TYPE_AUTO_TOPUP,
                addon_tokens_added=tokens,
                amount_currency="TWD",
                amount_value=Decimal(amount),
                triggered_by=TRIGGERED_BY_SYSTEM,
                reason="test seed",
            )
            await billing_repo.save(tx)

    _run(_seed())


# ---------------------------------------------------------------------------
# When: admin 呼叫
# ---------------------------------------------------------------------------


@when("admin 呼叫 GET /api/v1/admin/billing/dashboard")
def admin_get_dashboard(ctx, client):
    resp = client.get(
        "/api/v1/admin/billing/dashboard",
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp


@when(
    parsers.parse(
        "admin 呼叫 GET /api/v1/admin/billing/dashboard?"
        "start={start}&end={end}"
    )
)
def admin_get_dashboard_with_range(ctx, client, start, end):
    resp = client.get(
        f"/api/v1/admin/billing/dashboard?start={start}&end={end}",
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp


@given(parsers.parse('已建立非 admin 使用者 "{uname}" 綁定 {tname}'))
def create_non_admin_user(ctx, client, app, uname, tname):
    tenant_id = ctx["tenants"][tname]
    jwt_svc = app.container.jwt_service()
    token = jwt_svc.create_user_token(
        user_id=uname,
        tenant_id=tenant_id,
        role="tenant_admin",
    )
    ctx["non_admin_headers"] = {"Authorization": f"Bearer {token}"}


@when("regular-user 呼叫 GET /api/v1/admin/billing/dashboard")
def non_admin_get_dashboard(ctx, client):
    resp = client.get(
        "/api/v1/admin/billing/dashboard",
        headers=ctx["non_admin_headers"],
    )
    ctx["response"] = resp


# ---------------------------------------------------------------------------
# Then: 驗證
# ---------------------------------------------------------------------------


@then(parsers.parse("回應 monthly_revenue 應有 {n:d} 筆"))
def verify_monthly_count(ctx, n):
    resp = ctx["response"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["monthly_revenue"]) == n, (
        f"expected {n} monthly points, got {body['monthly_revenue']}"
    )


@then(parsers.parse("回應 by_plan 應有 {n:d} 筆"))
def verify_by_plan_count(ctx, n):
    body = ctx["response"].json()
    assert len(body["by_plan"]) == n, (
        f"expected {n} plan points, got {body['by_plan']}"
    )


@then(parsers.parse(
    '回應 top_tenants 第 {rank:d} 名應為 "{tname}" 累計營收 {amount:d}'
))
def verify_top_tenant(ctx, rank, tname, amount):
    body = ctx["response"].json()
    tops = body["top_tenants"]
    assert len(tops) >= rank, f"top_tenants 不足 {rank} 筆: {tops}"
    item = tops[rank - 1]
    assert item["tenant_name"] == tname, (
        f"rank {rank} expected {tname}, got {item['tenant_name']}"
    )
    assert Decimal(item["total_amount"]) == Decimal(amount), (
        f"{tname} expected {amount}, got {item['total_amount']}"
    )


@then(parsers.parse("回應 total_revenue 應為 {amount:d}"))
def verify_total_revenue(ctx, amount):
    body = ctx["response"].json()
    assert Decimal(body["total_revenue"]) == Decimal(amount), (
        f"total_revenue expected {amount}, got {body['total_revenue']}"
    )


@then(parsers.parse("回應 total_transactions 應為 {n:d}"))
def verify_total_transactions(ctx, n):
    body = ctx["response"].json()
    assert body["total_transactions"] == n


@then(parsers.parse("回應狀態碼應為 {code:d}"))
def verify_status_code(ctx, code):
    assert ctx["response"].status_code == code, (
        f"expected {code}, got {ctx['response'].status_code}"
    )


_ = current_year_month  # silence unused import lint
