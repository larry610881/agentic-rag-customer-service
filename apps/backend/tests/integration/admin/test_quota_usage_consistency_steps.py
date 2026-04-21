"""Quota / Usage Consistency — BDD Step Definitions (Route B)

驗證 GET /tenants/{id}/quota 回傳的 total_used_in_cycle 來自 token_usage_records
的即時 SUM，而非 ledger.total_used_in_cycle 累計欄位。

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #35
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import delete

from src.domain.rag.value_objects import TokenUsage
from src.infrastructure.db.models.token_ledger_model import TokenLedgerModel
from src.infrastructure.db.models.usage_record_model import UsageRecordModel

scenarios("integration/admin/quota_usage_consistency.feature")


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
# Given: usage seeding with explicit category
# ---------------------------------------------------------------------------


@given(parsers.parse('{tname} 已寫入 {n:d} tokens 用量 category "{cat}"'))
def seed_usage_with_category(ctx, tname, n, cat):
    container = ctx["app"].container
    record_usage = container.record_usage_use_case()
    _run(
        record_usage.execute(
            tenant_id=ctx["tenants"][tname],
            request_type=cat,
            usage=TokenUsage(
                model="test",
                input_tokens=n,
                output_tokens=0,
                total_tokens=n,
            ),
        )
    )


@given(parsers.parse('{tname} 本月已寫入 {n:d} tokens 用量 category "{cat}"'))
def seed_usage_current_cycle(ctx, tname, n, cat):
    # Alias of seed_usage_with_category — same semantics (record_usage writes NOW)
    seed_usage_with_category(ctx, tname, n, cat)


@given(parsers.parse('{tname} 於 {cycle} 已寫入 {n:d} tokens 用量'))
def seed_usage_historical(ctx, tname, cycle, n):
    """直接 insert token_usage_records 到指定歷史月份（cycle 格式 YYYY-MM）。

    不走 record_usage（那會用 NOW() + 觸發本月扣款）；直接操作 ORM 寫
    created_at 為指定月中的某天。
    """
    tenant_id = ctx["tenants"][tname]
    container = ctx["app"].container
    year, month = cycle.split("-")
    historical_date = datetime(
        int(year), int(month), 15, 12, 0, 0, tzinfo=timezone.utc
    )

    async def _insert():
        session = container.db_session()
        try:
            session.add(
                UsageRecordModel(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    request_type="rag",
                    model="test",
                    input_tokens=n,
                    output_tokens=0,
                    total_tokens=n,
                    estimated_cost=0.0,
                    cache_read_tokens=0,
                    cache_creation_tokens=0,
                    message_id=None,
                    bot_id=None,
                    created_at=historical_date,
                )
            )
            await session.commit()
        finally:
            await session.close()

    _run(_insert())


@given(parsers.parse('{tname} 設定 included_categories=[{quoted}]'))
def set_included_categories(ctx, client, tname, quoted):
    """quoted 例如 '"rag"' 或 '"rag", "chat_web"' → [...]"""
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
# When: query quota
# ---------------------------------------------------------------------------


@when(parsers.parse("admin 查詢 {tname} 本月 quota"))
def admin_query_quota(ctx, client, tname):
    tenant_id = ctx["tenants"][tname]
    resp = client.get(
        f"/api/v1/tenants/{tenant_id}/quota",
        headers=ctx["admin_headers"],
    )
    ctx["response"] = resp
    ctx["current_tenant"] = tname


# ---------------------------------------------------------------------------
# Then: assertions against response JSON
# ---------------------------------------------------------------------------


@then(parsers.parse("total_used_in_cycle 應為 {n:d}"))
def verify_total_used(ctx, n):
    resp = ctx["response"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_used_in_cycle"] == n, (
        f"total_used_in_cycle expected {n}, got {body['total_used_in_cycle']}"
    )


@then(parsers.parse("base_remaining 應為 {n:d}"))
def verify_base_remaining(ctx, n):
    body = ctx["response"].json()
    assert body["base_remaining"] == n, (
        f"base_remaining expected {n}, got {body['base_remaining']}"
    )


# ---------------------------------------------------------------------------
# Cleanup helpers (not used as BDD steps — internal only)
# ---------------------------------------------------------------------------


def _cleanup_ledgers_and_usage(ctx, tname):
    """Drop stale ledger + usage records for a tenant (used between scenarios)."""
    tenant_id = ctx["tenants"][tname]
    container = ctx["app"].container

    async def _del():
        session = container.db_session()
        try:
            await session.execute(
                delete(TokenLedgerModel).where(
                    TokenLedgerModel.tenant_id == tenant_id
                )
            )
            await session.execute(
                delete(UsageRecordModel).where(
                    UsageRecordModel.tenant_id == tenant_id
                )
            )
            await session.commit()
        finally:
            await session.close()

    _run(_del())
