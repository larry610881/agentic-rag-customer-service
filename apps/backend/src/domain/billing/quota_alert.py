"""QuotaAlertLog — 額度警示通知紀錄 (S-Token-Gov.3)

每個 (tenant_id, cycle, alert_type) 至多一筆（DB UNIQUE 約束保證冪等）。
警示通道目前僅 DB log；.3.5 SendGrid 整合後 delivered_to_email 才會被更新。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4


# Alert types
ALERT_TYPE_BASE_WARNING_80 = "base_warning_80"
ALERT_TYPE_BASE_EXHAUSTED_100 = "base_exhausted_100"


@dataclass
class QuotaAlertLog:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    cycle_year_month: str = ""
    alert_type: str = ""  # ALERT_TYPE_BASE_WARNING_80 | ALERT_TYPE_BASE_EXHAUSTED_100
    used_ratio: Decimal = field(default_factory=lambda: Decimal("0"))
    message: str = ""
    delivered_to_email: bool = False  # 預留給 .3.5 SendGrid 整合
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class QuotaAlertLogRepository(ABC):
    @abstractmethod
    async def save_if_new(
        self, alert: QuotaAlertLog
    ) -> QuotaAlertLog | None:
        """寫入警示；若 (tenant_id, cycle, alert_type) 已存在回 None。

        實作必須利用 DB UNIQUE 約束保證冪等 — cron 重跑同一 alert 不會重複寫。
        """
        ...

    @abstractmethod
    async def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[QuotaAlertLog]: ...

    @abstractmethod
    async def count_recent(
        self, tenant_id: str | None = None
    ) -> int: ...

    @abstractmethod
    async def find_by_tenant_and_cycle(
        self, tenant_id: str, cycle: str
    ) -> list[QuotaAlertLog]:
        """測試 + 排查用 — 不分 alert_type 全部回。"""
        ...

    @abstractmethod
    async def find_undelivered(
        self, *, limit: int = 100
    ) -> list[QuotaAlertLog]:
        """掃 delivered_to_email=False 的 row（cron dispatch 用）。S-Token-Gov.3.5"""
        ...

    @abstractmethod
    async def mark_delivered(self, alert_id: str) -> None:
        """寄成功（或無收件者）後標記。S-Token-Gov.3.5"""
        ...
