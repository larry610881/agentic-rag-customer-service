"""Regression（Issue #65）：指定 cycle 尚無 ledger 時 base_total 取方案額度，不是 0。

ea7cbb3 讓系統層額度總覽改走 ComputeTenantQuotaUseCase(cycle=...)，無 ledger 的分支
寫死 base_total=0 → 未啟用租戶顯示 0 / 0（dd7ea60 規格為方案基準額度）。
此路徑是唯讀預估：不得建立 ledger。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.application.quota.compute_tenant_quota_use_case import (
    ComputeTenantQuotaUseCase,
)


def _use_case(plan_base: int | None):
    tenant = SimpleNamespace(
        id=SimpleNamespace(value="t1"), plan="starter", included_categories=None
    )
    ensure_ledger = AsyncMock()
    ensure_ledger._ledger_repo.find_by_tenant_and_cycle = AsyncMock(return_value=None)
    ensure_ledger.plan_base_total = AsyncMock(return_value=plan_base)
    usage = AsyncMock()
    usage.sum_tokens_in_cycle = AsyncMock(return_value=0)
    usage.sum_billable_tokens_in_cycle = AsyncMock(return_value=0)
    topup = AsyncMock()
    topup.sum_amount_in_cycle = AsyncMock(return_value=0)
    uc = ComputeTenantQuotaUseCase(
        tenant_repository=AsyncMock(find_by_id=AsyncMock(return_value=tenant)),
        ensure_ledger=ensure_ledger,
        usage_repository=usage,
        topup_repository=topup,
    )
    return uc, ensure_ledger


def test_無_ledger_的_cycle_以方案額度為_base_且不建_ledger():
    uc, ensure_ledger = _use_case(10_000_000)
    snap = asyncio.run(uc.execute("t1", cycle="2026-09"))
    assert (snap.base_total, snap.base_remaining) == (10_000_000, 10_000_000)
    assert snap.cycle_year_month == "2026-09"
    ensure_ledger.execute.assert_not_awaited()


def test_方案不存在時_base_為_0():
    uc, _ = _use_case(None)
    snap = asyncio.run(uc.execute("t1", cycle="2026-09"))
    assert snap.base_total == 0
