"""Token Ledger 扣費 + 月度重置 — BDD Step Definitions (S-Token-Gov.2)

直接 call container 內的 use case 測試（避免跑真 LLM），
驗證 ledger 在不同情境的扣費 + carryover 行為。
"""

from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.ledger.entity import current_year_month
from src.domain.rag.value_objects import TokenUsage

scenarios("integration/admin/token_ledger.feature")


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
    ctx["tenant_id"] = resp.json()["id"]
    ctx["app"] = app

    # Assign plan
    assign = client.post(
        f"/api/v1/admin/plans/{plan_name}/assign/{ctx['tenant_id']}",
        headers=ctx["admin_headers"],
    )
    assert assign.status_code == 204, assign.text


# ---------------------------------------------------------------------------
# Scenario 1: 第一次扣費自動建本月 ledger
# ---------------------------------------------------------------------------


@when(parsers.parse(
    "record_usage 寫入 {n:d} tokens (category={cat}) 給 ledger-co"
))
def record_usage_with_category(ctx, n, cat):
    container = ctx["app"].container
    record_usage = container.record_usage_use_case()
    _run(
        record_usage.execute(
            tenant_id=ctx["tenant_id"],
            request_type=cat,
            usage=TokenUsage(
                model="test",
                input_tokens=n,
                output_tokens=0,
                total_tokens=n,
            ),
        )
    )


@when(parsers.parse("record_usage 寫入 {n:d} tokens 給 ledger-co"))
def record_usage_default_cat(ctx, n):
    container = ctx["app"].container
    record_usage = container.record_usage_use_case()
    _run(
        record_usage.execute(
            tenant_id=ctx["tenant_id"],
            request_type="rag",  # 預設用 rag
            usage=TokenUsage(
                model="test",
                input_tokens=n,
                output_tokens=0,
                total_tokens=n,
            ),
        )
    )


@then("該租戶本月 ledger 應存在")
def verify_ledger_exists(ctx):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    cycle = current_year_month()
    ledger = _run(
        ledger_repo.find_by_tenant_and_cycle(ctx["tenant_id"], cycle)
    )
    assert ledger is not None, f"ledger missing for {ctx['tenant_id']}/{cycle}"
    ctx["ledger"] = ledger


@then(parsers.parse("base_remaining 應為 {n:d}"))
def verify_base_remaining(ctx, n):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    cycle = current_year_month()
    ledger = _run(
        ledger_repo.find_by_tenant_and_cycle(ctx["tenant_id"], cycle)
    )
    assert ledger is not None, "ledger missing"
    assert ledger.base_remaining == n, (
        f"base_remaining: expected {n}, got {ledger.base_remaining}"
    )


@then(parsers.parse("total_used_in_cycle 應為 {n:d}"))
def verify_total_used(ctx, n):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    cycle = current_year_month()
    ledger = _run(
        ledger_repo.find_by_tenant_and_cycle(ctx["tenant_id"], cycle)
    )
    assert ledger is not None
    assert ledger.total_used_in_cycle == n


@then(parsers.parse("addon_remaining 應為 {n:d}"))
def verify_addon_remaining(ctx, n):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    cycle = current_year_month()
    ledger = _run(
        ledger_repo.find_by_tenant_and_cycle(ctx["tenant_id"], cycle)
    )
    assert ledger is not None
    assert ledger.addon_remaining == n, (
        f"addon_remaining: expected {n}, got {ledger.addon_remaining}"
    )


# ---------------------------------------------------------------------------
# Scenario 3: base 用完 — addon 變負（軟上限）
# ---------------------------------------------------------------------------


@given(parsers.parse(
    "ledger-co 本月 ledger base_remaining={base:d} addon_remaining={addon:d}"
))
def setup_ledger_with_state(ctx, base, addon):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    ensure = container.ensure_ledger_use_case()
    cycle = current_year_month()

    # 先建本月 ledger
    ledger = _run(ensure.execute(ctx["tenant_id"], "starter"))
    # 強制設定特定狀態
    ledger.base_remaining = base
    ledger.base_total = base if base > 0 else 10_000_000
    ledger.addon_remaining = addon
    ledger.total_used_in_cycle = 0
    _run(ledger_repo.save(ledger))


# ---------------------------------------------------------------------------
# Scenario 4: 月度重置 — addon 從上月 carryover
# ---------------------------------------------------------------------------


@given(parsers.parse(
    "ledger-co 上月 ledger addon_remaining={addon:d}"
))
def setup_last_month_ledger(ctx, addon):
    """直接寫入「上月」ledger row 模擬上月用過的狀態。

    用 test app 的 session factory（test DB）— 不可用 module-level
    async_session_factory（指向 dev DB）會 FK 失敗。
    """
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from sqlalchemy import delete

    from src.infrastructure.db.models.token_ledger_model import (
        TokenLedgerModel,
    )

    now = datetime.now(timezone.utc)
    if now.month == 1:
        last_cycle = f"{now.year - 1}-12"
    else:
        last_cycle = f"{now.year:04d}-{now.month - 1:02d}"
    cycle = current_year_month()
    tenant_id = ctx["tenant_id"]
    container = ctx["app"].container

    async def _setup():
        session = container.db_session()
        try:
            # 清本月 ledger（避免 background 跑掉）
            await session.execute(
                delete(TokenLedgerModel).where(
                    TokenLedgerModel.tenant_id == tenant_id,
                    TokenLedgerModel.cycle_year_month == cycle,
                )
            )
            session.add(
                TokenLedgerModel(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    cycle_year_month=last_cycle,
                    plan_name="starter",
                    base_total=10_000_000,
                    base_remaining=8_000_000,
                    addon_remaining=addon,
                    total_used_in_cycle=2_000_000,
                    created_at=now - timedelta(days=30),
                    updated_at=now - timedelta(days=1),
                )
            )
            await session.commit()
        finally:
            await session.close()

    _run(_setup())


@when("執行 ProcessMonthlyResetUseCase")
def run_monthly_reset(ctx):
    container = ctx["app"].container
    use_case = container.process_monthly_reset_use_case()
    ctx["reset_stats"] = _run(use_case.execute())


@then("應為 ledger-co 建本月新 ledger")
def verify_new_ledger_created(ctx):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    cycle = current_year_month()
    ledger = _run(
        ledger_repo.find_by_tenant_and_cycle(ctx["tenant_id"], cycle)
    )
    assert ledger is not None
    ctx["ledger"] = ledger


@then("本月 base_remaining 應等於 plan.base_monthly_tokens")
def verify_base_equals_plan(ctx):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    plan_repo = container.plan_repository()
    cycle = current_year_month()

    ledger = _run(
        ledger_repo.find_by_tenant_and_cycle(ctx["tenant_id"], cycle)
    )
    plan = _run(plan_repo.find_by_name("starter"))
    assert ledger.base_remaining == plan.base_monthly_tokens


@then(parsers.parse("本月 addon_remaining 應為 {n:d}"))
def verify_carryover(ctx, n):
    container = ctx["app"].container
    ledger_repo = container.token_ledger_repository()
    cycle = current_year_month()
    ledger = _run(
        ledger_repo.find_by_tenant_and_cycle(ctx["tenant_id"], cycle)
    )
    assert ledger.addon_remaining == n


# ---------------------------------------------------------------------------
# Scenario 5: included_categories 過濾
# ---------------------------------------------------------------------------


@given(parsers.parse(
    'ledger-co 設定 included_categories=[{quoted}]'
))
def set_included_categories(ctx, client, quoted):
    """quoted 例如 '"rag"' → 解析為 ["rag"]"""
    cats = [c.strip().strip('"') for c in quoted.split(",")]
    resp = client.patch(
        f"/api/v1/tenants/{ctx['tenant_id']}/config",
        json={"included_categories": cats},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 200, resp.text
