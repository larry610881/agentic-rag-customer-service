"""Ensure Ledger Use Case — S-Token-Gov.2 + Tier 1 T1.2 (Issue #42)

取得本月 ledger，若不存在則自動建立。addon carryover 從上月的用量 + topup
append-only log inline 算出（同 ComputeTenantQuotaUseCase 的 math），
寫成本月首筆 `carryover` topup 紀錄。

### Tier 1 T1.2 變更（2026-04-24）

- 舊版：`addon_carryover = last.addon_remaining if last else 0`
  → 讀 `ledger.addon_remaining` mutable 欄位，該欄位於 P4 後不再維護 → 永遠讀到 0
  → 每月跨月 cron 把租戶上月 addon 餘額「偷」清零

- 新版：inline 計算（SSOT 一致）
  ```
  last_billable = SUM(usage_records, last_cycle, included_categories)
  last_topup_sum = SUM(topups, last_cycle)
  last_overage = max(0, last_billable - last_base_total)
  carryover = last_topup_sum - last_overage
  ```
  寫成本月首筆 `reason="carryover"` topup。
  和 `ComputeTenantQuotaUseCase` 的 addon_remaining 計算邏輯保持一致（同 SSOT）。

### 為何 inline 而非呼叫 ComputeTenantQuotaUseCase

- 避免 DI 循環：ComputeQuota 的 `cycle=None` 路徑會呼叫 EnsureLedger，
  EnsureLedger 若反向呼叫 ComputeQuota → Python class body 順序 NameError
- math 簡單（4 行 SUM + 減法），複用 `UsageRepository` / `TokenLedgerTopupRepository`
"""

from __future__ import annotations

from src.domain.ledger.entity import (
    TokenLedger,
    current_year_month,
    previous_year_month,
)
from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.ledger.topup_entity import REASON_CARRYOVER, TokenLedgerTopup
from src.domain.ledger.topup_repository import TokenLedgerTopupRepository
from src.domain.plan.repository import PlanRepository
from src.domain.tenant.repository import TenantRepository
from src.domain.usage.repository import UsageRepository
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class EnsureLedgerUseCase:
    def __init__(
        self,
        ledger_repository: TokenLedgerRepository,
        plan_repository: PlanRepository,
        usage_repository: UsageRepository,
        topup_repository: TokenLedgerTopupRepository,
        tenant_repository: TenantRepository,
    ) -> None:
        self._ledger_repo = ledger_repository
        self._plan_repo = plan_repository
        self._usage_repo = usage_repository
        self._topup_repo = topup_repository
        self._tenant_repo = tenant_repository

    async def execute(self, tenant_id: str, plan_name: str) -> TokenLedger:
        cycle = current_year_month()
        existing = await self._ledger_repo.find_by_tenant_and_cycle(
            tenant_id, cycle
        )
        if existing:
            return existing

        # 從 plan 讀基準 base_total
        plan = await self._plan_repo.find_by_name(plan_name)
        base_total = plan.base_monthly_tokens if plan else 0
        if plan is None:
            logger.warning(
                "ledger.plan_not_found",
                tenant_id=tenant_id,
                plan_name=plan_name,
                action="creating zero-budget ledger",
            )

        # T1.2: 算上月 final addon_remaining 做 carryover
        carryover = await self._compute_carryover(tenant_id, cycle)

        # 建 ledger（mutable 欄位 dead weight 但 NOT NULL，填初始值）
        ledger = TokenLedger(
            tenant_id=tenant_id,
            cycle_year_month=cycle,
            plan_name=plan_name,
            base_total=base_total,
            base_remaining=base_total,
            addon_remaining=0,
            total_used_in_cycle=0,
        )
        await self._ledger_repo.save(ledger)

        # 繼承上月 addon（寫成本月 first carryover topup）
        if carryover != 0:
            await self._topup_repo.save(
                TokenLedgerTopup(
                    tenant_id=tenant_id,
                    cycle_year_month=cycle,
                    amount=carryover,
                    reason=REASON_CARRYOVER,
                )
            )

        logger.info(
            "ledger.created",
            tenant_id=tenant_id,
            cycle=cycle,
            plan=plan_name,
            base_total=base_total,
            carryover=carryover,
        )
        return ledger

    async def _compute_carryover(self, tenant_id: str, cycle: str) -> int:
        """計算上月 final addon_remaining（= 本月 carryover amount）。

        邏輯複製自 `ComputeTenantQuotaUseCase.execute`，保持 SSOT 一致：
            carryover = topup_sum(last) - max(0, billable(last) - base_total(last))
        """
        last_cycle = previous_year_month(cycle)

        try:
            last_ledger = await self._ledger_repo.find_by_tenant_and_cycle(
                tenant_id, last_cycle
            )
            last_base_total = last_ledger.base_total if last_ledger else 0

            tenant = await self._tenant_repo.find_by_id(tenant_id)
            if tenant is None:
                return 0

            billable_sum = await self._usage_repo.sum_billable_tokens_in_cycle(
                tenant_id, last_cycle, tenant.included_categories
            )
            topup_sum = await self._topup_repo.sum_amount_in_cycle(
                tenant_id, last_cycle
            )
            overage = max(0, billable_sum - last_base_total)
            return topup_sum - overage
        except Exception:
            logger.warning(
                "ledger.carryover_fallback_to_zero",
                tenant_id=tenant_id,
                last_cycle=last_cycle,
                exc_info=True,
            )
            return 0
