"""Compute Tenant Quota Use Case — S-Ledger-Unification P3

唯一的 quota 讀取入口。所有欄位從 token_usage_records + token_ledger_topups
即時算出，無 mutable state。結構上保證：

    base_total - base_remaining  ≡  min(billable, base_total)
    addon_remaining              =  topup_sum - max(0, billable - base_total)

即不可能 drift。取代原本的 GetTenantQuotaUseCase / ListAllTenantsQuotasUseCase
計算邏輯。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.domain.ledger.topup_repository import TokenLedgerTopupRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.tenant.repository import TenantRepository
from src.domain.usage.repository import UsageRepository


@dataclass(frozen=True)
class TenantQuotaSnapshot:
    tenant_id: str
    cycle_year_month: str
    plan_name: str
    base_total: int
    base_remaining: int  # = base_total - min(billable, base_total)
    addon_remaining: int  # = topup_sum - max(0, billable - base_total)
    total_remaining: int  # base_remaining + addon_remaining
    total_audit_in_cycle: int  # SUM(usage_records) 不 filter
    total_billable_in_cycle: int  # SUM(usage_records) with included_categories filter
    included_categories: list[str] | None


class ComputeTenantQuotaUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        ensure_ledger: EnsureLedgerUseCase,
        usage_repository: UsageRepository,
        topup_repository: TokenLedgerTopupRepository,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._ensure_ledger = ensure_ledger
        self._usage_repo = usage_repository
        self._topup_repo = topup_repository

    async def execute(
        self, tenant_id: str, cycle: str | None = None
    ) -> TenantQuotaSnapshot:
        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)

        if cycle is None:
            ledger = await self._ensure_ledger.execute(tenant_id, tenant.plan)
            target_cycle = ledger.cycle_year_month
            base_total = ledger.base_total
            plan_name = ledger.plan_name
        else:
            existing = (
                await self._ensure_ledger._ledger_repo.find_by_tenant_and_cycle(
                    tenant_id, cycle
                )
            )
            if existing:
                target_cycle = existing.cycle_year_month
                base_total = existing.base_total
                plan_name = existing.plan_name
            else:
                target_cycle = cycle
                base_total = 0
                plan_name = tenant.plan

        audit_total = await self._usage_repo.sum_tokens_in_cycle(
            tenant_id, target_cycle
        )
        billable_total = await self._usage_repo.sum_billable_tokens_in_cycle(
            tenant_id, target_cycle, tenant.included_categories
        )
        topup_sum = await self._topup_repo.sum_amount_in_cycle(
            tenant_id, target_cycle
        )

        base_used = min(billable_total, base_total)
        overage = max(0, billable_total - base_total)
        base_remaining = base_total - base_used
        addon_remaining = topup_sum - overage

        return TenantQuotaSnapshot(
            tenant_id=tenant_id,
            cycle_year_month=target_cycle,
            plan_name=plan_name,
            base_total=base_total,
            base_remaining=base_remaining,
            addon_remaining=addon_remaining,
            total_remaining=base_remaining + addon_remaining,
            total_audit_in_cycle=audit_total,
            total_billable_in_cycle=billable_total,
            included_categories=tenant.included_categories,
        )
