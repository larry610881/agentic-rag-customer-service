"""List All Tenants Quotas Use Case — S-Token-Gov.2.5

系統管理員視角：一次取得所有租戶在指定 cycle 的額度概況，
用於 `/admin/quota-overview` 頁。

策略：
- 3 query 取全（tenants / ledgers for cycle / plans），application 層 join
- 不為了顯示而建 ledger（避免 N 個 INSERT）— 沒 ledger 的租戶顯示 0 + has_ledger=False
- 計算邏輯與 GetTenantQuotaUseCase 對齊
  （base_remaining + addon_remaining = total_remaining）
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.plan.repository import PlanRepository
from src.domain.tenant.repository import TenantRepository
from src.domain.usage.repository import UsageRepository


@dataclass(frozen=True)
class TenantQuotaItem:
    tenant_id: str
    tenant_name: str
    plan_name: str
    cycle_year_month: str
    base_total: int
    base_remaining: int
    addon_remaining: int
    total_remaining: int  # base_remaining + addon_remaining
    total_used_in_cycle: int
    included_categories: list[str] | None
    has_ledger: bool  # False = 該 cycle 該租戶從未扣過費（顯示為 0）


class ListAllTenantsQuotasUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        ledger_repository: TokenLedgerRepository,
        plan_repository: PlanRepository,
        usage_repository: UsageRepository,
    ) -> None:
        self._tenants = tenant_repository
        self._ledgers = ledger_repository
        self._plans = plan_repository
        self._usage = usage_repository

    async def execute(self, cycle: str) -> list[TenantQuotaItem]:
        tenants = await self._tenants.find_all()
        ledgers = await self._ledgers.find_all_for_cycle(cycle)
        plans = await self._plans.find_all(include_inactive=True)

        ledger_by_tenant = {ledger.tenant_id: ledger for ledger in ledgers}
        plan_by_name = {plan.name: plan for plan in plans}

        items: list[TenantQuotaItem] = []
        for tenant in tenants:
            tenant_id = tenant.id.value
            ledger = ledger_by_tenant.get(tenant_id)
            plan = plan_by_name.get(tenant.plan)

            # Route B: total_used_in_cycle 由 usage_records SUM 取得
            # （每個 tenant 一次 query，N+1；tenants 數多再優化 batch）
            total_used = await self._usage.sum_tokens_in_cycle(
                tenant_id=tenant_id, cycle_year_month=cycle
            )

            if ledger is not None:
                items.append(
                    TenantQuotaItem(
                        tenant_id=tenant_id,
                        tenant_name=tenant.name,
                        plan_name=ledger.plan_name,
                        cycle_year_month=ledger.cycle_year_month,
                        base_total=ledger.base_total,
                        base_remaining=ledger.base_remaining,
                        addon_remaining=ledger.addon_remaining,
                        total_remaining=ledger.total_remaining,
                        total_used_in_cycle=total_used,
                        included_categories=tenant.included_categories,
                        has_ledger=True,
                    )
                )
                continue

            base_total = plan.base_monthly_tokens if plan is not None else 0
            items.append(
                TenantQuotaItem(
                    tenant_id=tenant_id,
                    tenant_name=tenant.name,
                    plan_name=tenant.plan,
                    cycle_year_month=cycle,
                    base_total=base_total,
                    base_remaining=base_total,
                    addon_remaining=0,
                    total_remaining=base_total,
                    total_used_in_cycle=total_used,
                    included_categories=tenant.included_categories,
                    has_ledger=False,
                )
            )

        return items
