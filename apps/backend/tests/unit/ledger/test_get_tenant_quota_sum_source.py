"""GetTenantQuotaUseCase — 驗證 total_used_in_cycle 來自 usage_records SUM

Route B 核心不變性：DTO 的 total_used_in_cycle 欄位由
UsageRepository.sum_tokens_in_cycle 計算，而非讀 ledger.total_used_in_cycle
（後者是累計狀態，會與部署前歷史 usage drift）。

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #35
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.ledger.get_tenant_quota_use_case import GetTenantQuotaUseCase
from src.domain.ledger.entity import TokenLedger
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mk_tenant(tid: str = "t-1") -> Tenant:
    return Tenant(
        id=TenantId(value=tid),
        name="T",
        plan="starter",
        included_categories=None,
    )


def _mk_ledger(
    tid: str = "t-1",
    cycle: str = "2026-04",
    ledger_total_used: int = 0,
) -> TokenLedger:
    return TokenLedger(
        tenant_id=tid,
        cycle_year_month=cycle,
        plan_name="starter",
        base_total=10_000_000,
        base_remaining=10_000_000 - ledger_total_used,
        addon_remaining=0,
        total_used_in_cycle=ledger_total_used,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _build_use_case(
    tenant: Tenant,
    ledger: TokenLedger,
    sum_from_usage: int,
) -> tuple[GetTenantQuotaUseCase, AsyncMock]:
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=tenant)

    ensure_ledger = AsyncMock()
    ensure_ledger.execute = AsyncMock(return_value=ledger)

    usage_repo = AsyncMock()
    usage_repo.sum_tokens_in_cycle = AsyncMock(return_value=sum_from_usage)

    uc = GetTenantQuotaUseCase(
        tenant_repository=tenant_repo,
        ensure_ledger=ensure_ledger,
        usage_repository=usage_repo,
    )
    return uc, usage_repo


def test_total_used_in_cycle_comes_from_usage_sum_not_ledger():
    """Route B：即使 ledger.total_used_in_cycle 是 99（假值），
    DTO 回傳值應等於 usage_repo.sum_tokens_in_cycle 回傳的 500。"""
    tenant = _mk_tenant()
    ledger = _mk_ledger(ledger_total_used=99)  # 故意與 usage_repo 不同
    uc, usage_repo = _build_use_case(tenant, ledger, sum_from_usage=500)

    result = _run(uc.execute(tenant_id="t-1"))

    assert result.total_used_in_cycle == 500  # 來自 usage_repo SUM
    assert result.total_used_in_cycle != ledger.total_used_in_cycle  # 不是 ledger 欄位
    usage_repo.sum_tokens_in_cycle.assert_awaited_once_with(
        tenant_id="t-1", cycle_year_month="2026-04"
    )


def test_zero_usage_in_cycle_returns_zero_total_used():
    tenant = _mk_tenant()
    ledger = _mk_ledger(ledger_total_used=0)
    uc, usage_repo = _build_use_case(tenant, ledger, sum_from_usage=0)

    result = _run(uc.execute(tenant_id="t-1"))

    assert result.total_used_in_cycle == 0
    usage_repo.sum_tokens_in_cycle.assert_awaited_once()


def test_historical_drift_recovered_by_sum():
    """模擬 Carrefour 案例：ledger.total_used_in_cycle = 14,912（部署後才開始扣），
    但實際本月用量 usage_records SUM = 295,992 → DTO 顯示應為後者。"""
    tenant = _mk_tenant()
    ledger = _mk_ledger(ledger_total_used=14_912)
    uc, usage_repo = _build_use_case(tenant, ledger, sum_from_usage=295_992)

    result = _run(uc.execute(tenant_id="t-1"))

    assert result.total_used_in_cycle == 295_992


def test_base_and_addon_remaining_still_read_from_ledger():
    """Route B 只改 total_used_in_cycle 的來源；base/addon 餘額仍讀 ledger
    （因為那是真實的累計狀態，不能用 SUM 推算）。"""
    tenant = _mk_tenant()
    ledger = _mk_ledger(ledger_total_used=14_912)  # base_remaining = 10M - 14912
    uc, _ = _build_use_case(tenant, ledger, sum_from_usage=295_992)

    result = _run(uc.execute(tenant_id="t-1"))

    assert result.base_remaining == 10_000_000 - 14_912
    assert result.addon_remaining == 0


def test_tenant_not_found_raises():
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=None)
    uc = GetTenantQuotaUseCase(
        tenant_repository=tenant_repo,
        ensure_ledger=AsyncMock(),
        usage_repository=AsyncMock(),
    )
    from src.domain.shared.exceptions import EntityNotFoundError

    with pytest.raises(EntityNotFoundError):
        _run(uc.execute(tenant_id="nonexistent"))
