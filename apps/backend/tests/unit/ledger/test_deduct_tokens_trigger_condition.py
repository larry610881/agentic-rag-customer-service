"""DeductTokensUseCase — auto_topup trigger 條件 regression guard (Token-Gov.7 D)

2026-04-21 Carrefour 實測發現 bug：
原先 trigger 條件只有 `addon_remaining <= 0`，但「初始 addon=0 + base 充足」時
第一次扣費就會誤觸發 topup，產生虛假 +5M / 1500 TWD billing。

修正後條件：`base_remaining <= 0 AND addon_remaining <= 0`（真的餘額耗盡才補）。
本測試保證未來不會再回退。

Issue: #37
Plan: .claude/plans/b-bug-delightful-starlight.md
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from src.application.ledger.deduct_tokens_use_case import DeductTokensUseCase
from src.domain.ledger.entity import TokenLedger


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mk_ledger(base_remaining: int, addon_remaining: int) -> TokenLedger:
    return TokenLedger(
        tenant_id="t-1",
        cycle_year_month="2026-04",
        plan_name="starter",
        base_total=10_000_000,
        base_remaining=base_remaining,
        addon_remaining=addon_remaining,
        total_used_in_cycle=10_000_000 - base_remaining,
    )


def _build(ledger: TokenLedger):
    ledger_repo = AsyncMock()
    ledger_repo.save = AsyncMock()

    ensure = AsyncMock()
    ensure.execute = AsyncMock(return_value=ledger)

    topup = AsyncMock()
    topup.execute = AsyncMock(return_value=None)

    plan_repo = AsyncMock()
    plan_repo.find_by_name = AsyncMock()

    uc = DeductTokensUseCase(
        ledger_repository=ledger_repo,
        ensure_ledger=ensure,
        topup_addon=topup,
        plan_repository=plan_repo,
    )
    return uc, topup, plan_repo


# --- Carrefour 複刻：初始 addon=0 + base 充足 → 絕不 topup ---
def test_no_topup_when_base_sufficient_and_addon_zero():
    """Carrefour bug 場景：
    ledger 剛建（base=10M, addon=0 無上月 carryover），第一次扣費 1000 tokens。
    修正後：base_remaining 還有 ~10M，addon=0 但不該 topup（因為 base 還夠）。
    """
    ledger = _mk_ledger(base_remaining=10_000_000, addon_remaining=0)
    uc, topup, plan_repo = _build(ledger)

    _run(uc.execute(tenant_id="t-1", tokens=1000, plan_name="starter"))

    # 應只扣 base，不觸發 topup
    assert ledger.base_remaining == 10_000_000 - 1000
    assert ledger.addon_remaining == 0  # 沒動
    topup.execute.assert_not_awaited()
    plan_repo.find_by_name.assert_not_awaited()


# --- base 被扣到剛好耗盡（=0）+ addon=0 → 應 topup ---
def test_topup_when_both_base_and_addon_exhausted():
    """標準 S-Token-Gov.3 情境：扣完讓 base 到 0、addon 也耗盡 → topup。"""
    ledger = _mk_ledger(base_remaining=500, addon_remaining=0)
    uc, topup, plan_repo = _build(ledger)

    # topup.execute 要 mock 回一個非 None 的結果讓 triggered_topup = True
    topup.execute = AsyncMock(return_value=(ledger, "fake_tx"))
    plan_repo.find_by_name = AsyncMock(return_value="fake_plan")

    _run(uc.execute(tenant_id="t-1", tokens=500, plan_name="starter"))

    # base 耗盡、addon 也是 0，trigger 條件滿足
    assert ledger.base_remaining == 0
    topup.execute.assert_awaited_once()


# --- base 充足但 addon 被扣到負（不合邏輯但理論可能）→ 不 topup ---
def test_no_topup_when_only_addon_negative_but_base_has_tokens():
    """防禦性：就算 addon 因為歷史資料異常為負，只要 base 仍有餘額就不 topup。"""
    ledger = _mk_ledger(base_remaining=1_000_000, addon_remaining=-100)
    uc, topup, _ = _build(ledger)

    _run(uc.execute(tenant_id="t-1", tokens=100, plan_name="starter"))

    topup.execute.assert_not_awaited()


# --- base 真的用完、addon 已經有餘額（上月 carryover）→ 不 topup ---
def test_no_topup_when_base_exhausted_but_addon_positive():
    """base 用完後進入 addon 扣款階段，addon 仍有餘額 → 不 topup。"""
    ledger = _mk_ledger(base_remaining=0, addon_remaining=2_000_000)
    uc, topup, _ = _build(ledger)

    _run(uc.execute(tenant_id="t-1", tokens=500, plan_name="starter"))

    # addon 被扣 500 (從 2M → 1,999,500)，仍為正，不 topup
    assert ledger.addon_remaining == 2_000_000 - 500
    topup.execute.assert_not_awaited()
