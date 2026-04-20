"""System-level Quota Overview — BDD Step Definitions (S-Token-Gov.2.5)

驗證 GET /api/v1/admin/tenants/quotas 在不同情境下回傳所有租戶的當月
（或指定 cycle）額度概況，並對非 admin 使用者拒絕存取。
"""

from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.ledger.entity import current_year_month
from src.domain.rag.value_objects import TokenUsage

scenarios("integration/admin/quota_overview.feature")


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
# Usage seeding
# ---------------------------------------------------------------------------


@given(parsers.parse("{tname} 已寫入 {n:d} tokens 用量"))
def seed_usage(ctx, tname, n):
    container = ctx["app"].container
    record_usage = container.record_usage_use_case()
    tenant_id = ctx["tenants"][tname]
    _run(
        record_usage.execute(
            tenant_id=tenant_id,
            request_type="rag",
            usage=TokenUsage(
                model="test",
                input_tokens=n,
                output_tokens=0,
                total_tokens=n,
            ),
        )
    )


# ---------------------------------------------------------------------------
# When: admin 呼叫
# ---------------------------------------------------------------------------


@when("admin 呼叫 GET /api/v1/admin/tenants/quotas")
def admin_list_quotas(ctx, client):
    resp = client.get(
        "/api/v1/admin/tenants/quotas",
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp


@when(
    parsers.parse(
        "admin 呼叫 GET /api/v1/admin/tenants/quotas?cycle={cycle}"
    )
)
def admin_list_quotas_with_cycle(ctx, client, cycle):
    resp = client.get(
        f"/api/v1/admin/tenants/quotas?cycle={cycle}",
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp


@given(parsers.parse('已建立非 admin 使用者 "{uname}" 綁定 {tname}'))
def create_non_admin_user(ctx, client, app, uname, tname):
    """建立 tenant_admin 角色 (非 system_admin) 的使用者並取得 token。"""
    tenant_id = ctx["tenants"][tname]
    jwt_svc = app.container.jwt_service()
    token = jwt_svc.create_user_token(
        user_id=uname,
        tenant_id=tenant_id,
        role="tenant_admin",  # 非 system_admin → 應 403
    )
    ctx["non_admin_headers"] = {"Authorization": f"Bearer {token}"}


@when("regular-user 呼叫 GET /api/v1/admin/tenants/quotas")
def non_admin_list_quotas(ctx, client):
    resp = client.get(
        "/api/v1/admin/tenants/quotas",
        headers=ctx["non_admin_headers"],
    )
    ctx["response"] = resp


# ---------------------------------------------------------------------------
# Then: 驗證
# ---------------------------------------------------------------------------


@then(parsers.parse("回應應包含 {n:d} 筆租戶資料"))
def verify_response_count(ctx, n):
    resp = ctx["response"]
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == n, f"expected {n} items, got {len(items)}: {items}"


def _find(ctx, tname):
    tenant_id = ctx["tenants"][tname]
    for item in ctx["response"].json():
        if item["tenant_id"] == tenant_id:
            return item
    raise AssertionError(f"tenant {tname} ({tenant_id}) not found in response")


@then(parsers.parse('租戶 "{tname}" 的 has_ledger 應為 {flag}'))
def verify_has_ledger(ctx, tname, flag):
    expected = flag == "True"
    item = _find(ctx, tname)
    assert item["has_ledger"] is expected, (
        f"{tname}.has_ledger expected {expected}, got {item['has_ledger']}"
    )


@then(parsers.parse('租戶 "{tname}" 的 total_used_in_cycle 應為 {n:d}'))
def verify_used(ctx, tname, n):
    item = _find(ctx, tname)
    assert item["total_used_in_cycle"] == n, (
        f"{tname}.total_used_in_cycle expected {n}, "
        f"got {item['total_used_in_cycle']}"
    )


@then(parsers.parse('租戶 "{tname}" 的 base_total 應等於 plan.base_monthly_tokens'))
def verify_base_total_matches_plan(ctx, tname):
    item = _find(ctx, tname)
    # quota-gamma 綁 starter (base_monthly_tokens=10_000_000)
    assert item["base_total"] == 10_000_000, (
        f"{tname}.base_total expected 10000000, got {item['base_total']}"
    )


@then("所有租戶的 has_ledger 應為 False")
def verify_all_no_ledger(ctx):
    for item in ctx["response"].json():
        assert item["has_ledger"] is False, (
            f"tenant {item['tenant_id']} unexpectedly has_ledger=True"
        )


@then("所有租戶的 total_used_in_cycle 應為 0")
def verify_all_zero_used(ctx):
    for item in ctx["response"].json():
        assert item["total_used_in_cycle"] == 0, (
            f"tenant {item['tenant_id']} unexpectedly used > 0"
        )


@then(parsers.parse("回應狀態碼應為 {code:d}"))
def verify_status_code(ctx, code):
    assert ctx["response"].status_code == code, (
        f"expected {code}, got {ctx['response'].status_code}: {ctx['response'].text}"
    )


# ---------------------------------------------------------------------------
# Suppress unused-import lint
# ---------------------------------------------------------------------------

_ = current_year_month  # imported for parity with token_ledger steps
