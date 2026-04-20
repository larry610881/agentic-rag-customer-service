"""Ensure Ledger Use Case — S-Token-Gov.2

取得本月 ledger，若不存在則自動建立（addon 從上月 carryover）。
給 DeductTokensUseCase + GetTenantQuotaUseCase + ProcessMonthlyResetUseCase 共用。
"""

from src.domain.ledger.entity import TokenLedger, current_year_month
from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.plan.repository import PlanRepository
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class EnsureLedgerUseCase:
    def __init__(
        self,
        ledger_repository: TokenLedgerRepository,
        plan_repository: PlanRepository,
    ) -> None:
        self._ledger_repo = ledger_repository
        self._plan_repo = plan_repository

    async def execute(self, tenant_id: str, plan_name: str) -> TokenLedger:
        cycle = current_year_month()  # "YYYY-MM"
        existing = await self._ledger_repo.find_by_tenant_and_cycle(
            tenant_id, cycle
        )
        if existing:
            return existing

        # 第一次本月 — 從 plan 讀基準 + 上月 addon carryover
        plan = await self._plan_repo.find_by_name(plan_name)
        base_total = plan.base_monthly_tokens if plan else 0
        if plan is None:
            logger.warning(
                "ledger.plan_not_found",
                tenant_id=tenant_id,
                plan_name=plan_name,
                action="creating zero-budget ledger",
            )

        # addon 從最近一筆 ledger 結轉
        last = await self._ledger_repo.find_latest_by_tenant(tenant_id)
        addon_carryover = last.addon_remaining if last else 0

        ledger = TokenLedger(
            tenant_id=tenant_id,
            cycle_year_month=cycle,
            plan_name=plan_name,
            base_total=base_total,
            base_remaining=base_total,
            addon_remaining=addon_carryover,
            total_used_in_cycle=0,
        )
        await self._ledger_repo.save(ledger)
        logger.info(
            "ledger.created",
            tenant_id=tenant_id,
            cycle=cycle,
            plan=plan_name,
            base_total=base_total,
            addon_carryover=addon_carryover,
        )
        return ledger
