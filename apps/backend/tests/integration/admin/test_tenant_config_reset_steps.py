"""Tenant Config included_categories Reset — BDD Step Definitions (Bug 1+2 修復)

驗證 PATCH /tenants/{id}/config 對 included_categories 三種輸入的語意：
- 未帶欄位 → 維持既有值
- 顯式 null → 重置為 NULL（全計入）
- 空陣列 [] → 全不計入（POC 免計費）

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #35
"""
from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/admin/tenant_config_reset.feature")


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
        "description": "POC test",
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
def seed_plans(ctx, client, admin_headers):
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
# Given: pre-state setup via PATCH
# ---------------------------------------------------------------------------


def _parse_list_literal(s: str) -> list[str] | None:
    """Parse a feature-file JSON-ish list.

    支援：
      '[]'             → []
      '["rag"]'        → ["rag"]
      '["rag", "chat_web"]' → ["rag", "chat_web"]
      'null' / 'None'  → None
    """
    s = s.strip()
    if s.lower() in ("null", "none"):
        return None
    if s == "[]":
        return []
    # 剝掉外層 [] 後 split 處理
    inner = s.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    if not inner.strip():
        return []
    return [tok.strip().strip('"').strip("'") for tok in inner.split(",")]


@given(parsers.parse("{tname} 當前 included_categories={value}"))
def given_current_included(ctx, client, tname, value):
    """把 tenant 的 included_categories 先設成 feature 指定的初始值。

    value 是 feature 原樣字串，例如 'null' / '["rag"]' / '[]'。
    null → 不 PATCH（reuse default）；否則 PATCH 寫入。
    """
    parsed = _parse_list_literal(value)
    if parsed is None:
        # tenant 剛建立時 included_categories 預設就是 NULL，無需 PATCH
        # 但為保險起見先嘗試 reset（忽略失敗，有 bug 未修時會不成功）
        return

    tenant_id = ctx["tenants"][tname]
    resp = client.patch(
        f"/api/v1/tenants/{tenant_id}/config",
        json={"included_categories": parsed},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# When: admin PATCH tenant config
# ---------------------------------------------------------------------------


@when(parsers.parse("admin PATCH {tname} config 送 included_categories=null"))
def patch_with_explicit_null(ctx, client, tname):
    tenant_id = ctx["tenants"][tname]
    resp = client.patch(
        f"/api/v1/tenants/{tenant_id}/config",
        json={"included_categories": None},
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp
    ctx["current_tenant"] = tname


@when(parsers.parse(
    "admin PATCH {tname} config 只送 monthly_token_limit={n:d}"
))
def patch_only_limit(ctx, client, tname, n):
    tenant_id = ctx["tenants"][tname]
    resp = client.patch(
        f"/api/v1/tenants/{tenant_id}/config",
        json={"monthly_token_limit": n},
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp
    ctx["current_tenant"] = tname


@when(parsers.parse("admin PATCH {tname} config 送 included_categories=[]"))
def patch_with_empty_list(ctx, client, tname):
    tenant_id = ctx["tenants"][tname]
    resp = client.patch(
        f"/api/v1/tenants/{tenant_id}/config",
        json={"included_categories": []},
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp
    ctx["current_tenant"] = tname


# ---------------------------------------------------------------------------
# Then: verify tenant state via response body
# ---------------------------------------------------------------------------


@then(parsers.parse("{tname} 的 included_categories 應為 {expected}"))
def verify_included_categories(ctx, tname, expected):
    resp = ctx["response"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    actual = body.get("included_categories")
    parsed_expected = _parse_list_literal(expected)
    assert actual == parsed_expected, (
        f"{tname}.included_categories expected {parsed_expected!r}, got {actual!r}"
    )


@then(parsers.parse("{tname} 的 included_categories 仍為 {expected}"))
def verify_included_categories_unchanged(ctx, tname, expected):
    verify_included_categories(ctx, tname, expected)


@then(parsers.parse("{tname} 的 monthly_token_limit 應為 {n:d}"))
def verify_monthly_limit(ctx, tname, n):
    body = ctx["response"].json()
    actual = body.get("monthly_token_limit")
    assert actual == n, (
        f"{tname}.monthly_token_limit expected {n}, got {actual}"
    )
