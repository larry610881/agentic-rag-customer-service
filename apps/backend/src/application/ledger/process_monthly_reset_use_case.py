"""Process Monthly Reset Use Case — S-Token-Gov.2

每月 1 日 cron 觸發：為所有租戶建本月新 ledger，addon 從上月 carryover。
arq cron job (worker.py monthly_reset_task) 呼叫。

冪等：若本月 ledger 已建（如使用者月初活動先觸發 EnsureLedger），跳過。
"""

from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.domain.ledger.entity import current_year_month
from src.domain.ledger.repository import TokenLedgerRepository
from src.domain.tenant.repository import TenantRepository
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProcessMonthlyResetUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        ledger_repository: TokenLedgerRepository,
        ensure_ledger: EnsureLedgerUseCase,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._ledger_repo = ledger_repository
        self._ensure_ledger = ensure_ledger

    async def execute(self) -> dict:
        """為所有租戶建本月新 ledger。回傳統計：{processed, created, skipped, failed}"""
        cycle = current_year_month()
        tenants = await self._tenant_repo.find_all()

        stats = {
            "cycle": cycle,
            "processed": 0,
            "created": 0,
            "skipped": 0,
            "failed": 0,
        }

        for tenant in tenants:
            stats["processed"] += 1
            try:
                existing = await self._ledger_repo.find_by_tenant_and_cycle(
                    tenant.id.value, cycle
                )
                if existing:
                    stats["skipped"] += 1
                    continue

                await self._ensure_ledger.execute(tenant.id.value, tenant.plan)
                stats["created"] += 1
            except Exception:
                stats["failed"] += 1
                logger.warning(
                    "monthly_reset.tenant_failed",
                    tenant_id=tenant.id.value,
                    cycle=cycle,
                    exc_info=True,
                )

        logger.info("monthly_reset.done", **stats)
        return stats
