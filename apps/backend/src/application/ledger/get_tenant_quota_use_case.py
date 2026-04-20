"""Get Tenant Quota Use Case — S-Token-Gov.2

回傳租戶本月額度狀態（base/addon/used）。若本月 ledger 不存在，
即時 EnsureLedgerUseCase 建一個並回傳。

GET /api/v1/tenants/{tenant_id}/quota 使用。
"""

from dataclasses import dataclass

from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.tenant.repository import TenantRepository


@dataclass(frozen=True)
class TenantQuotaResult:
    cycle_year_month: str
    plan_name: str
    base_total: int
    base_remaining: int
    addon_remaining: int
    total_remaining: int  # = base_remaining + addon_remaining
    total_used_in_cycle: int
    included_categories: list[str] | None


class GetTenantQuotaUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        ensure_ledger: EnsureLedgerUseCase,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._ensure_ledger = ensure_ledger

    async def execute(self, tenant_id: str) -> TenantQuotaResult:
        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)

        ledger = await self._ensure_ledger.execute(tenant_id, tenant.plan)

        return TenantQuotaResult(
            cycle_year_month=ledger.cycle_year_month,
            plan_name=ledger.plan_name,
            base_total=ledger.base_total,
            base_remaining=ledger.base_remaining,
            addon_remaining=ledger.addon_remaining,
            total_remaining=ledger.total_remaining,
            total_used_in_cycle=ledger.total_used_in_cycle,
            included_categories=tenant.included_categories,
        )
