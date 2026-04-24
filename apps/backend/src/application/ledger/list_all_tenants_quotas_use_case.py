"""List All Tenants Quotas Use Case — S-Ledger-Unification P5

系統管理員視角：一次取得所有租戶在指定 cycle 的額度概況，
用於 `/admin/quota-overview` 頁。

P5 變更：底層計算統一走 ComputeTenantQuotaUseCase，保證與租戶視角零 drift。
新增 total_audit_in_cycle + total_billable_in_cycle 並列欄位，供 admin 看
「平台吸收量 = audit - billable」。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.quota.compute_tenant_quota_use_case import (
    ComputeTenantQuotaUseCase,
)
from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.tenant.repository import TenantRepository


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
    total_audit_in_cycle: int  # 平台真實消耗（含不計費）
    total_billable_in_cycle: int  # 影響計費（= 租戶看到的本月已用）
    included_categories: list[str] | None
    has_ledger: bool  # False = 該 cycle 該租戶從未建過 ledger


class ListAllTenantsQuotasUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        ledger_repository: TokenLedgerRepository,
        compute_quota: ComputeTenantQuotaUseCase,
    ) -> None:
        self._tenants = tenant_repository
        self._ledgers = ledger_repository
        self._compute_quota = compute_quota

    async def execute(self, cycle: str) -> list[TenantQuotaItem]:
        tenants = await self._tenants.find_all()
        ledgers = await self._ledgers.find_all_for_cycle(cycle)
        ledger_by_tenant = {ledger.tenant_id: ledger for ledger in ledgers}

        items: list[TenantQuotaItem] = []
        for tenant in tenants:
            tenant_id = tenant.id.value
            has_ledger = tenant_id in ledger_by_tenant
            snapshot = await self._compute_quota.execute(tenant_id, cycle=cycle)
            items.append(
                TenantQuotaItem(
                    tenant_id=tenant_id,
                    tenant_name=tenant.name,
                    plan_name=snapshot.plan_name,
                    cycle_year_month=snapshot.cycle_year_month,
                    base_total=snapshot.base_total,
                    base_remaining=snapshot.base_remaining,
                    addon_remaining=snapshot.addon_remaining,
                    total_remaining=snapshot.total_remaining,
                    total_audit_in_cycle=snapshot.total_audit_in_cycle,
                    total_billable_in_cycle=snapshot.total_billable_in_cycle,
                    included_categories=snapshot.included_categories,
                    has_ledger=has_ledger,
                )
            )
        return items
