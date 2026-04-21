"""Two-Page Consistency — BDD Step Definitions (Token-Gov.6)

驗證 Token 用量頁與本月額度頁的加總不變性：無論 usage 組成（含 cache tokens）
或 filter 設定如何變，兩頁顯示的本月累計用量永遠相等。

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #36
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.db.models.usage_record_model import UsageRecordModel

scenarios("integration/admin/two_page_consistency.feature")


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
# Usage seeding — 直接寫 token_usage_records（繞過 record_usage，便於精準控 cache）
# ---------------------------------------------------------------------------


@given(parsers.parse(
    '{tname} 本月寫入 usage input={inp:d} output={out:d} '
    'cache_read={cr:d} cache_creation={cc:d} category "{cat}"'
))
def seed_usage_full(ctx, tname, inp, out, cr, cc, cat):
    tenant_id = ctx["tenants"][tname]
    container = ctx["app"].container

    async def _insert():
        session = container.db_session()
        try:
            session.add(
                UsageRecordModel(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    request_type=cat,
                    model="test",
                    input_tokens=inp,
                    output_tokens=out,
                    estimated_cost=0.0,
                    cache_read_tokens=cr,
                    cache_creation_tokens=cc,
                    message_id=None,
                    bot_id=None,
                )
            )
            await session.commit()
        finally:
            await session.close()

    _run(_insert())


@given(parsers.parse(
    '{tname} 本月寫入 usage input={inp:d} output={out:d} category "{cat}"'
))
def seed_usage_no_cache(ctx, tname, inp, out, cat):
    seed_usage_full(ctx, tname, inp, out, 0, 0, cat)


@given(parsers.parse('{tname} 設定 included_categories=[{quoted}]'))
def set_included_categories(ctx, client, tname, quoted):
    """quoted 例如 '"rag"' → ["rag"]"""
    if quoted.strip() == "":
        cats: list[str] = []
    else:
        cats = [c.strip().strip('"') for c in quoted.split(",")]
    resp = client.patch(
        f"/api/v1/tenants/{ctx['tenants'][tname]}/config",
        json={"included_categories": cats},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# When: 調兩個 API
# ---------------------------------------------------------------------------


@when("調用兩個 API 並比對加總")
def call_both_apis(ctx, client):
    _call_both(ctx, client, ctx["tenants"][list(ctx["tenants"].keys())[0]])


@when(parsers.parse("調用 {tname} 的兩個 API 並比對加總"))
def call_both_apis_tname(ctx, client, tname):
    _call_both(ctx, client, ctx["tenants"][tname])


def _call_both(ctx, client, tenant_id: str):
    """取 Token 用量頁的 by-bot 總和 + 本月額度頁的 total_used_in_cycle。"""
    # Token 用量頁：GET /api/v1/usage/by-bot — 模擬前端 reduce(row.total_tokens)
    by_bot = client.get(
        "/api/v1/usage/by-bot",
        headers=_tenant_headers(ctx, tenant_id),
    )
    assert by_bot.status_code == 200, by_bot.text
    rows = by_bot.json()
    usage_page_total = sum(r["total_tokens"] for r in rows)
    ctx["usage_page_total"] = usage_page_total

    # 本月額度頁：GET /api/v1/tenants/{id}/quota
    quota = client.get(
        f"/api/v1/tenants/{tenant_id}/quota",
        headers=_tenant_headers(ctx, tenant_id),
    )
    assert quota.status_code == 200, quota.text
    ctx["quota_total_used"] = quota.json()["total_used_in_cycle"]


def _tenant_headers(ctx, tenant_id: str) -> dict[str, str]:
    """為該 tenant 建 tenant_admin token。

    /usage/by-bot 是 self-scope API（走 JWT 內 tenant_id），必須用該 tenant
    專屬的 token 才能看到該 tenant 的 usage。admin_headers 會 scope 到 admin
    自己的 tenant，看不到 consistency-co 等租戶的 usage。
    """
    cache = ctx.setdefault("_tenant_tokens", {})
    if tenant_id in cache:
        return cache[tenant_id]
    jwt_svc = ctx["app"].container.jwt_service()
    token = jwt_svc.create_user_token(
        user_id=f"test-admin-{tenant_id}",
        tenant_id=tenant_id,
        role="tenant_admin",
    )
    headers = {"Authorization": f"Bearer {token}"}
    cache[tenant_id] = headers
    return headers


# ---------------------------------------------------------------------------
# Then: 兩頁加總必相等
# ---------------------------------------------------------------------------


@then(parsers.parse("Token 用量頁總和應等於 {n:d}"))
def verify_usage_page_total(ctx, n):
    actual = ctx.get("usage_page_total")
    assert actual == n, (
        f"Token 用量頁加總 expected {n}, got {actual}"
    )


@then(parsers.parse("本月額度頁 total_used_in_cycle 應等於 {n:d}"))
def verify_quota_total_used(ctx, n):
    actual = ctx.get("quota_total_used")
    assert actual == n, (
        f"本月額度頁 total_used_in_cycle expected {n}, got {actual}"
    )
