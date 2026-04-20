"""Get Billing Dashboard Use Case — S-Token-Gov.4

合併 3 個聚合 query (monthly_revenue / by_plan / top_tenants) +
補 tenant_name 給前端儀表板。

策略：
- 3 個聚合 + 1 個 tenant 列表 = 4 query（避免 SQL JOIN 跨 BC repo 邊界）
- 跨範圍 total 由 application 層加總（避免額外 SQL）
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.domain.billing.aggregates import (
    MonthlyRevenuePoint,
    PlanRevenuePoint,
)
from src.domain.billing.repository import BillingTransactionRepository
from src.domain.tenant.repository import TenantRepository


@dataclass(frozen=True)
class TopTenantItem:
    tenant_id: str
    tenant_name: str
    total_amount: Decimal
    transaction_count: int


@dataclass(frozen=True)
class BillingDashboardResult:
    monthly_revenue: list[MonthlyRevenuePoint]
    by_plan: list[PlanRevenuePoint]
    top_tenants: list[TopTenantItem]
    total_revenue: Decimal
    total_transactions: int
    cycle_start: str
    cycle_end: str


class GetBillingDashboardUseCase:
    def __init__(
        self,
        billing_transaction_repository: BillingTransactionRepository,
        tenant_repository: TenantRepository,
    ) -> None:
        self._billing_repo = billing_transaction_repository
        self._tenant_repo = tenant_repository

    async def execute(
        self,
        *,
        start_cycle: str,
        end_cycle: str,
        top_n: int = 10,
    ) -> BillingDashboardResult:
        monthly = await self._billing_repo.aggregate_monthly_revenue(
            start_cycle=start_cycle, end_cycle=end_cycle,
        )
        by_plan = await self._billing_repo.aggregate_by_plan(
            start_cycle=start_cycle, end_cycle=end_cycle,
        )
        top_raw = await self._billing_repo.aggregate_top_tenants(
            start_cycle=start_cycle, end_cycle=end_cycle, limit=top_n,
        )
        tenants = await self._tenant_repo.find_all()
        name_by_id = {t.id.value: t.name for t in tenants}

        top_tenants = [
            TopTenantItem(
                tenant_id=p.tenant_id,
                tenant_name=name_by_id.get(p.tenant_id, ""),
                total_amount=p.total_amount,
                transaction_count=p.transaction_count,
            )
            for p in top_raw
        ]

        total_revenue = sum(
            (m.total_amount for m in monthly), Decimal("0")
        )
        total_transactions = sum(m.transaction_count for m in monthly)

        return BillingDashboardResult(
            monthly_revenue=monthly,
            by_plan=by_plan,
            top_tenants=top_tenants,
            total_revenue=total_revenue,
            total_transactions=total_transactions,
            cycle_start=start_cycle,
            cycle_end=end_cycle,
        )
