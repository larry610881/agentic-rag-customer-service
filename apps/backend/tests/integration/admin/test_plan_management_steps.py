"""Plan Template CRUD + Assign — BDD Step Definitions (S-Token-Gov.1)

注意：integration test 用獨立 test DB，沒有跑 migration seed，
所以每個 scenario 透過 background step 自己 seed 三個 plan。
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/admin/plan_management.feature")


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


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Background — admin login + seed 3 plans
# ---------------------------------------------------------------------------


@given("admin 已登入並 seed 三個方案")
def admin_logged_in_and_seed(ctx, client, admin_headers):
    ctx["admin_headers"] = admin_headers
    ctx["plan_ids"] = {}
    for plan_data in SEED_PLANS:
        resp = client.post(
            "/api/v1/admin/plans",
            json=plan_data,
            headers=admin_headers,
        )
        # 接受 201 (建立) 或 409 (既有)
        if resp.status_code == 201:
            ctx["plan_ids"][plan_data["name"]] = resp.json()["id"]
        elif resp.status_code == 409:
            list_resp = client.get(
                "/api/v1/admin/plans", headers=admin_headers
            )
            for p in list_resp.json():
                if p["name"] == plan_data["name"]:
                    ctx["plan_ids"][plan_data["name"]] = p["id"]
                    break
        else:
            raise AssertionError(
                f"Unexpected {resp.status_code}: {resp.text}"
            )


# ---------------------------------------------------------------------------
# List plans
# ---------------------------------------------------------------------------


@when("admin 列出所有方案")
def list_plans(ctx, client):
    ctx["resp"] = client.get(
        "/api/v1/admin/plans", headers=ctx["admin_headers"]
    )


@then("應回 200")
def verify_200(ctx):
    assert ctx["resp"].status_code == 200, ctx["resp"].text


@then(parsers.parse('列表應包含 "{a}" "{b}" "{c}" 三個方案'))
def verify_listed(ctx, a, b, c):
    names = {p["name"] for p in ctx["resp"].json()}
    assert {a, b, c}.issubset(names), f"missing: {{{a}, {b}, {c}}} - {names}"


# ---------------------------------------------------------------------------
# Create plan
# ---------------------------------------------------------------------------


@when(parsers.parse(
    'admin 建立方案 "{name}" base={base:d} base_price={price:d}'
))
def create_plan(ctx, client, name, base, price):
    ctx["resp"] = client.post(
        "/api/v1/admin/plans",
        json={
            "name": name,
            "base_monthly_tokens": base,
            "addon_pack_tokens": base // 2,
            "base_price": price,
            "addon_price": price // 2,
            "currency": "TWD",
            "description": f"test {name}",
        },
        headers=ctx["admin_headers"],
    )


@then("應回 201")
def verify_201(ctx):
    assert ctx["resp"].status_code == 201, ctx["resp"].text


@then(parsers.parse('回傳的 plan name 應為 "{name}"'))
def verify_created_name(ctx, name):
    assert ctx["resp"].json()["name"] == name


@then("應回 409")
def verify_409(ctx):
    assert ctx["resp"].status_code == 409, ctx["resp"].text


# ---------------------------------------------------------------------------
# Update plan
# ---------------------------------------------------------------------------


@when(parsers.parse(
    'admin 編輯方案 "{name}" 設 base_monthly_tokens={n:d}'
))
def update_plan(ctx, client, name, n):
    plan_id = ctx["plan_ids"][name]
    ctx["plan_id"] = plan_id
    ctx["resp"] = client.patch(
        f"/api/v1/admin/plans/{plan_id}",
        json={"base_monthly_tokens": n},
        headers=ctx["admin_headers"],
    )


@then(parsers.parse("base_monthly_tokens 應為 {n:d}"))
def verify_update(ctx, n):
    assert ctx["resp"].json()["base_monthly_tokens"] == n


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


@when(parsers.parse('admin 刪除方案 "{name}" force=false'))
def soft_delete(ctx, client, name):
    plan_id = ctx["plan_ids"][name]
    ctx["plan_id"] = plan_id
    ctx["resp"] = client.delete(
        f"/api/v1/admin/plans/{plan_id}",
        headers=ctx["admin_headers"],
    )


@then("應回 204")
def verify_204(ctx):
    assert ctx["resp"].status_code == 204, ctx["resp"].text


@then("該 plan is_active 應為 false")
def verify_inactive(ctx, client):
    resp = client.get(
        f"/api/v1/admin/plans/{ctx['plan_id']}", headers=ctx["admin_headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Assign plan to tenant
# ---------------------------------------------------------------------------


@given(parsers.parse('已建立租戶 "{tname}"'))
def create_tenant_for_assign(ctx, client, tname):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": tname},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    ctx["tenant_id"] = resp.json()["id"]


@when(parsers.parse('admin 將 "{plan_name}" 指派給 "{tname}"'))
def assign_plan(ctx, client, plan_name, tname):
    ctx["resp"] = client.post(
        f"/api/v1/admin/plans/{plan_name}/assign/{ctx['tenant_id']}",
        headers=ctx["admin_headers"],
    )


@then(parsers.parse('tenant 的 plan 應為 "{plan_name}"'))
def verify_tenant_plan(ctx, client, plan_name):
    resp = client.get(
        f"/api/v1/tenants/{ctx['tenant_id']}", headers=ctx["admin_headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == plan_name


# ---------------------------------------------------------------------------
# Tenant-level permission denial
# ---------------------------------------------------------------------------


@given(parsers.parse('已建立並登入租戶 "{tname}"'))
def create_tenant_login(ctx, client, tname):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": tname},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 201
    tenant_id = resp.json()["id"]
    token_resp = client.post(
        "/api/v1/auth/token", json={"tenant_id": tenant_id}
    )
    assert token_resp.status_code == 200
    ctx["user_headers"] = {
        "Authorization": f"Bearer {token_resp.json()['access_token']}"
    }


@when(parsers.parse("{tname} 嘗試列出所有方案"))
def user_list_plans(ctx, client, tname):
    ctx["resp"] = client.get(
        "/api/v1/admin/plans", headers=ctx["user_headers"]
    )


@then("應回 403")
def verify_403(ctx):
    assert ctx["resp"].status_code == 403, ctx["resp"].text
