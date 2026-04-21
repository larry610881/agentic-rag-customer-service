"""Get Tenant Quota Use Case — S-Token-Gov.2 (+ Route B: total_used 改從 usage SUM)

回傳租戶本月額度狀態（base/addon/used）。若本月 ledger 不存在，
即時 EnsureLedgerUseCase 建一個並回傳。

GET /api/v1/tenants/{tenant_id}/quota 使用。

### Route B 不變性（2026-04）

`total_used_in_cycle` 由 `UsageRepository.sum_tokens_in_cycle()` 即時計算，
而非讀 `ledger.total_used_in_cycle`（那是 hook 累計狀態，會與部署前歷史 usage drift）。
這讓「Token 用量」與「本月額度」兩頁顯示值結構上同一份資料。

`base_remaining` / `addon_remaining` 仍讀 ledger（那是真實累計，不能用 SUM 推算）。
"""

from dataclasses import dataclass

from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.tenant.repository import TenantRepository
from src.domain.usage.repository import UsageRepository


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
        usage_repository: UsageRepository,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._ensure_ledger = ensure_ledger
        self._usage_repo = usage_repository

    async def execute(self, tenant_id: str) -> TenantQuotaResult:
        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)

        ledger = await self._ensure_ledger.execute(tenant_id, tenant.plan)

        # Route B: 從 token_usage_records 即時 SUM，取代 ledger.total_used_in_cycle
        total_used = await self._usage_repo.sum_tokens_in_cycle(
            tenant_id=tenant_id,
            cycle_year_month=ledger.cycle_year_month,
        )

        return TenantQuotaResult(
            cycle_year_month=ledger.cycle_year_month,
            plan_name=ledger.plan_name,
            base_total=ledger.base_total,
            base_remaining=ledger.base_remaining,
            addon_remaining=ledger.addon_remaining,
            total_remaining=ledger.total_remaining,
            total_used_in_cycle=total_used,
            included_categories=tenant.included_categories,
        )
