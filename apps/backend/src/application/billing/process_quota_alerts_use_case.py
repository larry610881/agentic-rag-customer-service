"""Process Quota Alerts Use Case — S-Token-Gov.3

每天由 arq cron 觸發：掃所有租戶本月 ledger，達 80% / 100% 寫 alert log。
冪等：QuotaAlertLogRepository.save_if_new 利用 DB UNIQUE 約束擋重複。
"""

from __future__ import annotations

import logging
from decimal import Decimal

from src.domain.billing.quota_alert import (
    ALERT_TYPE_BASE_EXHAUSTED_100,
    ALERT_TYPE_BASE_WARNING_80,
    QuotaAlertLog,
    QuotaAlertLogRepository,
)
from src.domain.ledger.entity import current_year_month
from src.domain.ledger.repository import TokenLedgerRepository

logger = logging.getLogger(__name__)


THRESHOLD_WARNING = Decimal("0.8")
THRESHOLD_EXHAUSTED = Decimal("1.0")


def _format_pct(ratio: Decimal) -> str:
    pct = ratio * Decimal("100")
    return f"{pct:.1f}%"


class ProcessQuotaAlertsUseCase:
    def __init__(
        self,
        ledger_repository: TokenLedgerRepository,
        alert_repository: QuotaAlertLogRepository,
    ) -> None:
        self._ledger_repo = ledger_repository
        self._alert_repo = alert_repository

    async def execute(self) -> dict[str, int]:
        cycle = current_year_month()
        ledgers = await self._ledger_repo.find_all_for_cycle(cycle)
        stats = {"checked": 0, "warnings": 0, "exhausted": 0}

        for ledger in ledgers:
            stats["checked"] += 1
            if ledger.base_total <= 0:
                continue
            used = ledger.base_total - ledger.base_remaining
            ratio = Decimal(used) / Decimal(ledger.base_total)

            if ratio >= THRESHOLD_EXHAUSTED:
                created = await self._alert_repo.save_if_new(
                    QuotaAlertLog(
                        tenant_id=ledger.tenant_id,
                        cycle_year_month=cycle,
                        alert_type=ALERT_TYPE_BASE_EXHAUSTED_100,
                        used_ratio=ratio,
                        message=f"Base 額度已耗盡 ({_format_pct(ratio)})",
                    )
                )
                if created is not None:
                    stats["exhausted"] += 1

            if ratio >= THRESHOLD_WARNING:
                created = await self._alert_repo.save_if_new(
                    QuotaAlertLog(
                        tenant_id=ledger.tenant_id,
                        cycle_year_month=cycle,
                        alert_type=ALERT_TYPE_BASE_WARNING_80,
                        used_ratio=ratio,
                        message=f"Base 額度已用 {_format_pct(ratio)}",
                    )
                )
                if created is not None:
                    stats["warnings"] += 1

        logger.info(
            "process_quota_alerts.done",
            extra={"cycle": cycle, "stats": stats},
        )
        return stats
