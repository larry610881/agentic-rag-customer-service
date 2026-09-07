"""點數制計價 BDD Step Definitions（Issue #74）

AsyncMock repository、無真 DB。RecordUsageUseCase 透過 CachedBillingContextProvider
讀方案 / 倍率 / 匯率，寫入 UsageRecord.points。
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.billing.billing_context import CachedBillingContextProvider
from src.application.billing.points_estimate import estimate_points
from src.application.billing.topup_addon_use_case import TopupAddonUseCase
from src.application.quota.compute_tenant_quota_use_case import (
    ComputeTenantQuotaUseCase,
)
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.billing.points import ModelPoints
from src.domain.billing.settings import BillingSettings
from src.domain.ledger.entity import TokenLedger
from src.domain.plan.entity import BillingMode, Plan
from src.domain.plan.value_objects import PlanCategoryMultiplier
from src.domain.rag.value_objects import TokenUsage
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId
from src.domain.usage.repository import UsageRepository

scenarios("unit/billing/points_billing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(
        side_effect=lambda tid: Tenant(id=TenantId(value=tid), plan="starter")
    )
    plan_repo = AsyncMock()
    plan_repo.find_by_name = AsyncMock(return_value=Plan(name="starter"))
    multiplier_repo = AsyncMock()
    multiplier_repo.list_for_plan = AsyncMock(return_value=[])
    settings_repo = AsyncMock()
    settings_repo.get = AsyncMock(return_value=None)
    pricing_cache = MagicMock()
    pricing_cache.lookup = MagicMock(return_value=None)
    pricing_cache.lookup_points = MagicMock(return_value=None)
    usage_repo = AsyncMock(spec=UsageRepository)
    saved: list = []
    usage_repo.save = AsyncMock(side_effect=lambda r: saved.append(r))
    provider = CachedBillingContextProvider(
        tenant_repo_factory=lambda: tenant_repo,
        plan_repo_factory=lambda: plan_repo,
        multiplier_repo_factory=lambda: multiplier_repo,
        settings_repo_factory=lambda: settings_repo,
    )
    return {
        "tenant_repo": tenant_repo,
        "plan_repo": plan_repo,
        "multiplier_repo": multiplier_repo,
        "settings_repo": settings_repo,
        "pricing_cache": pricing_cache,
        "usage_repo": usage_repo,
        "saved": saved,
        "provider": provider,
        "plan": Plan(name="starter"),
    }


def _set_plan(ctx, plan: Plan) -> None:
    ctx["plan"] = plan
    ctx["plan_repo"].find_by_name = AsyncMock(return_value=plan)
    ctx["tenant_repo"].find_by_id = AsyncMock(
        side_effect=lambda tid: Tenant(id=TenantId(value=tid), plan=plan.name)
    )
    ctx["provider"].invalidate(None)


def _use_case(ctx) -> RecordUsageUseCase:
    return RecordUsageUseCase(
        usage_repository=ctx["usage_repo"],
        pricing_cache=ctx["pricing_cache"],
        billing_context=ctx["provider"],
    )


# ---------------------------------------------------------------------------
# given
# ---------------------------------------------------------------------------


@given(parsers.parse("平台點數匯率為每點 {rate} 美元"))
def platform_rate(ctx, rate):
    ctx["settings_repo"].get = AsyncMock(
        return_value=BillingSettings(usd_per_point=Decimal(rate))
    )


@given(parsers.parse('點數制方案 "{name}" 每月 {points:d} 點、預設倍率 {mult}'))
def points_plan(ctx, name, points, mult):
    _set_plan(ctx, Plan(
        name=name, billing_mode=BillingMode.POINTS, monthly_points=points,
        default_category_multiplier=Decimal(mult),
    ))


@given(parsers.parse('點數制方案 "{name}" 每月 {points:d} 點、加購包 {pack:d} 點'))
def points_plan_with_pack(ctx, name, points, pack):
    _set_plan(ctx, Plan(
        name=name, billing_mode=BillingMode.POINTS, monthly_points=points,
        addon_pack_points=pack,
    ))


@given(parsers.parse('token 制方案 "{name}"'))
def token_plan(ctx, name):
    _set_plan(ctx, Plan(name=name, base_monthly_tokens=100_000))


@given(parsers.parse(
    '模型 "{model}" 設定點數表 輸入每千 {ppi} 點、輸出每千 {ppo} 點'
))
def model_points(ctx, model, ppi, ppo):
    points = ModelPoints(Decimal(ppi), Decimal(ppo))
    ctx["pricing_cache"].lookup_points = MagicMock(
        side_effect=lambda model_spec, at: points if model_spec == model else None
    )


@given(parsers.parse('方案 "{name}" 類別 "{category}" 倍率 {mult}'))
def category_multiplier(ctx, name, category, mult):
    existing = list(ctx.get("multipliers", []))
    existing.append(PlanCategoryMultiplier(ctx["plan"].id, category, Decimal(mult)))
    ctx["multipliers"] = existing
    ctx["multiplier_repo"].list_for_plan = AsyncMock(return_value=existing)
    ctx["provider"].invalidate(None)


@given(parsers.parse('租戶 "{tenant}" 本月已用 {used:d} 點且加購 {topup:d} 點'))
def points_used_and_topup(ctx, tenant, used, topup):
    ctx["points_used"] = used
    ctx["topup_points"] = topup


# ---------------------------------------------------------------------------
# when
# ---------------------------------------------------------------------------


@when(parsers.parse(
    '租戶 "{tenant}" 以模型 "{model}" 記錄 {inp:d} 輸入 {out:d} 輸出 tokens '
    '成本 {cost} 美元 類別 "{category}"'
))
def record(ctx, tenant, model, inp, out, cost, category):
    _run(_use_case(ctx).execute(
        tenant_id=tenant,
        request_type=category,
        usage=TokenUsage(
            model=model, input_tokens=inp, output_tokens=out,
            estimated_cost=float(cost),
        ),
    ))


@when(parsers.parse(
    '租戶 "{tenant}" 切換到點數制方案 "{name}" 每月 {points:d} 點、預設倍率 {mult}'
))
def switch_plan(ctx, tenant, name, points, mult):
    points_plan(ctx, name, points, mult)


@when(parsers.parse('租戶 "{tenant}" 記錄含 {reasoning:d} 推理 tokens 的用量'))
def record_with_reasoning(ctx, tenant, reasoning):
    _run(_use_case(ctx).execute(
        tenant_id=tenant,
        request_type="chat_web",
        usage=TokenUsage(
            model="openai:gpt-5.1", input_tokens=100, output_tokens=500,
            estimated_cost=0.01, reasoning_tokens=reasoning,
        ),
    ))


@when(parsers.parse('計算租戶 "{tenant}" 的配額'))
def compute_quota(ctx, tenant):
    plan = ctx["plan"]
    ensure_ledger = MagicMock()
    ensure_ledger.execute = AsyncMock(return_value=TokenLedger(
        tenant_id=tenant, cycle_year_month="2026-09", plan_name=plan.name,
        base_total=plan.base_monthly_tokens, base_remaining=plan.base_monthly_tokens,
    ))
    usage_repo = AsyncMock()
    usage_repo.sum_tokens_in_cycle = AsyncMock(return_value=0)
    usage_repo.sum_billable_tokens_in_cycle = AsyncMock(return_value=0)
    usage_repo.sum_points_in_cycle = AsyncMock(return_value=ctx.get("points_used", 0))
    topup_repo = AsyncMock()
    topup_repo.sum_amount_in_cycle = AsyncMock(return_value=0)
    topup_repo.sum_points_in_cycle = AsyncMock(return_value=ctx.get("topup_points", 0))
    uc = ComputeTenantQuotaUseCase(
        tenant_repository=ctx["tenant_repo"],
        ensure_ledger=ensure_ledger,
        usage_repository=usage_repo,
        topup_repository=topup_repo,
        billing_context=ctx["provider"],
    )
    ctx["snapshot"] = _run(uc.execute(tenant))


@when(parsers.parse('對租戶 "{tenant}" 執行自動展延'))
def run_topup(ctx, tenant):
    topup_repo = AsyncMock()
    topup_repo.find_in_cycle = AsyncMock(return_value=[])
    saved: list = []
    topup_repo.save = AsyncMock(side_effect=lambda t: saved.append(t))
    ledger_repo = AsyncMock()
    ledger_repo.find_by_tenant_and_cycle = AsyncMock(return_value=TokenLedger(
        id="ledger-1", tenant_id=tenant, cycle_year_month="2026-09",
    ))
    uc = TopupAddonUseCase(
        topup_repository=topup_repo,
        billing_transaction_repository=AsyncMock(),
        ledger_repository=ledger_repo,
    )
    ctx["topup_result"] = _run(uc.execute(
        tenant_id=tenant, cycle_year_month="2026-09", plan=ctx["plan"],
    ))
    ctx["topups_saved"] = saved


# ---------------------------------------------------------------------------
# then
# ---------------------------------------------------------------------------


@then(parsers.parse("寫入的用量紀錄 points 為 {points:d}"))
def saved_points(ctx, points):
    assert ctx["saved"], "no usage record saved"
    assert ctx["saved"][-1].points == points


@then(parsers.parse("寫入的用量紀錄 input_tokens 為 {tokens:d}"))
def saved_input_tokens(ctx, tokens):
    assert ctx["saved"][-1].input_tokens == tokens


@then(parsers.parse("寫入的用量紀錄 reasoning_tokens 為 {tokens:d}"))
def saved_reasoning_tokens(ctx, tokens):
    assert ctx["saved"][-1].reasoning_tokens == tokens


@then(parsers.parse("第 {index:d} 筆用量紀錄 points 為 {points:d}"))
def nth_points(ctx, index, points):
    assert ctx["saved"][index - 1].points == points


@then(parsers.parse("方案只從資料庫讀取 {count:d} 次"))
def plan_read_count(ctx, count):
    assert ctx["plan_repo"].find_by_name.await_count == count


@then(parsers.parse('配額快照 billing_mode 為 "{mode}"'))
def snapshot_mode(ctx, mode):
    assert ctx["snapshot"].billing_mode == mode


@then(parsers.parse(
    "配額快照 points_total 為 {total:d}、points_used 為 {used:d}、"
    "points_remaining 為 {remaining:d}"
))
def snapshot_points(ctx, total, used, remaining):
    snap = ctx["snapshot"]
    assert (snap.points_total, snap.points_used, snap.points_remaining) == (
        total, used, remaining
    )


@then(parsers.parse("寫入的加購紀錄 amount_points 為 {points:d}"))
def topup_points(ctx, points):
    assert ctx["topups_saved"], "no topup saved"
    assert ctx["topups_saved"][-1].amount_points == points


@when(parsers.parse('估算租戶 "{tenant}" 類別 "{category}" 成本 {cost} 美元'))
def run_estimate(ctx, tenant, category, cost):
    ctx["estimate"] = _run(
        estimate_points(ctx["provider"], tenant, category, float(cost))
    )


@then(parsers.parse('估算結果 billing_mode 為 "{mode}" 且 est_points 為 {points:d}'))
def estimate_result(ctx, mode, points):
    assert ctx["estimate"] == {"billing_mode": mode, "est_points": points}
