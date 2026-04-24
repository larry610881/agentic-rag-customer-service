"""EnsureLedger carryover BDD Steps — S-Ledger-Unification Tier 1 T1.2"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.domain.ledger.topup_entity import TokenLedgerTopup

scenarios("unit/ledger/ensure_ledger_carryover.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx() -> dict:
    """Shared context for each scenario.

    last_cycle_state model：
      - last_base_total: int（from last ledger.base_total）
      - last_billable: int（total billable usage in last cycle）
      - last_topup_sum: int（sum of all topups in last cycle）
      → carryover = last_topup_sum - max(0, last_billable - last_base_total)
    """
    return {
        "has_last_ledger": False,
        "last_base_total": 10_000_000,
        "last_billable": 0,
        "last_topup_sum": 0,
        "existing_ledgers": {},  # cycle -> TokenLedger-like SimpleNamespace
        "saved_topups": [],
        "saved_ledgers": [],
    }


def _build_use_case(ctx: dict) -> EnsureLedgerUseCase:
    # ledger_repo
    ledger_repo = AsyncMock()

    async def find_ledger(tenant_id, cycle):
        # 用途 1: current cycle → 應 return None（走 create path）
        # 用途 2: last_cycle → return existing last ledger（if has_last_ledger）
        if cycle in ctx["existing_ledgers"]:
            return ctx["existing_ledgers"][cycle]
        if ctx.get("has_last_ledger") and cycle == ctx.get("_last_cycle_key"):
            return SimpleNamespace(
                id="last-ledger-id",
                tenant_id=tenant_id,
                cycle_year_month=cycle,
                base_total=ctx["last_base_total"],
            )
        return None

    async def save_ledger(ledger):
        ctx["existing_ledgers"][ledger.cycle_year_month] = ledger
        ctx["saved_ledgers"].append(ledger)
        return ledger

    ledger_repo.find_by_tenant_and_cycle = AsyncMock(side_effect=find_ledger)
    ledger_repo.save = AsyncMock(side_effect=save_ledger)

    # plan_repo
    plan_repo = AsyncMock()
    plan_repo.find_by_name = AsyncMock(return_value=SimpleNamespace(
        name="starter", base_monthly_tokens=ctx.get("base_total", 10_000_000)
    ))

    # tenant_repo
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=SimpleNamespace(
        id=SimpleNamespace(value=ctx["tenant_id"]),
        plan="starter",
        included_categories=None,  # 全部計入
    ))

    # usage_repo
    usage_repo = AsyncMock()
    usage_repo.sum_billable_tokens_in_cycle = AsyncMock(
        return_value=ctx["last_billable"]
    )

    # topup_repo
    topup_repo = AsyncMock()
    topup_repo.sum_amount_in_cycle = AsyncMock(
        return_value=ctx["last_topup_sum"]
    )

    async def save_topup(topup):
        ctx["saved_topups"].append(topup)
        return topup

    topup_repo.save = AsyncMock(side_effect=save_topup)

    return EnsureLedgerUseCase(
        ledger_repository=ledger_repo,
        plan_repository=plan_repo,
        usage_repository=usage_repo,
        topup_repository=topup_repo,
        tenant_repository=tenant_repo,
    )


def _setup_last_state_for_addon(ctx: dict, target_addon: int) -> None:
    """給定想要的 last final addon_remaining，反推 last_billable / last_topup_sum。

    公式：addon = topup_sum - max(0, billable - base_total)
    策略：保持 billable <= base_total 則 overage=0，topup_sum=addon。
          若 addon < 0 需要 overage > 0，用 billable = base_total + |addon|, topup_sum=0。
    """
    if target_addon >= 0:
        ctx["last_billable"] = 0
        ctx["last_topup_sum"] = target_addon
    else:
        # addon 為負：需要 overage = -target_addon，topup_sum 可為 0
        ctx["last_billable"] = ctx["last_base_total"] + (-target_addon)
        ctx["last_topup_sum"] = 0


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('租戶 "{tname}" 綁定 plan "{plan}" base_total={base:d}'))
def seed_tenant(ctx, tname, plan, base):
    ctx["tenant_id"] = tname
    ctx["plan"] = plan
    ctx["base_total"] = base
    ctx["last_base_total"] = base  # 上月 base_total 同 plan snapshot


@given(
    parsers.parse(
        'carry-co 在 {cycle} 的 final addon_remaining 為 {amount:d}'
    )
)
def set_last_addon(ctx, cycle, amount):
    ctx["has_last_ledger"] = True
    ctx["_last_cycle_key"] = cycle
    _setup_last_state_for_addon(ctx, amount)


@given("carry-co 歷史上沒有任何 ledger")
def no_prior_ledger(ctx):
    ctx["has_last_ledger"] = False
    ctx["last_billable"] = 0
    ctx["last_topup_sum"] = 0


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('建立 carry-co 在 {cycle} 的 ledger'))
def create_ledger_at(ctx, cycle, monkeypatch):
    from src.application.ledger import ensure_ledger_use_case as mod

    monkeypatch.setattr(mod, "current_year_month", lambda: cycle)

    uc = _build_use_case(ctx)
    _run(uc.execute(ctx["tenant_id"], ctx["plan"]))


@when(parsers.parse('再次呼叫 EnsureLedger 建立 carry-co 在 {cycle} 的 ledger'))
def call_ensure_ledger_again(ctx, cycle, monkeypatch):
    from src.application.ledger import ensure_ledger_use_case as mod

    monkeypatch.setattr(mod, "current_year_month", lambda: cycle)

    uc = _build_use_case(ctx)
    _run(uc.execute(ctx["tenant_id"], ctx["plan"]))


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(
    parsers.parse(
        'carry-co 在 {cycle} 應有 {n:d} 筆 reason="{reason}" 的 topup amount={amount:d}'
    )
)
def verify_carryover_topup(ctx, cycle, n, reason, amount):
    matching: list[TokenLedgerTopup] = [
        t for t in ctx["saved_topups"]
        if t.cycle_year_month == cycle
        and t.reason == reason
        and t.amount == amount
    ]
    assert len(matching) == n, (
        f"expected {n} topup(s) cycle={cycle} reason={reason} amount={amount}, "
        f"got {len(matching)}. All saved: "
        f"{[(t.cycle_year_month, t.reason, t.amount) for t in ctx['saved_topups']]}"
    )


@then(parsers.parse('carry-co 在 {cycle} 應有 {n:d} 筆 carryover topup'))
def verify_carryover_count(ctx, cycle, n):
    matching = [
        t for t in ctx["saved_topups"]
        if t.cycle_year_month == cycle and t.reason == "carryover"
    ]
    assert len(matching) == n, (
        f"expected {n} carryover topups in {cycle}, got {len(matching)}"
    )
