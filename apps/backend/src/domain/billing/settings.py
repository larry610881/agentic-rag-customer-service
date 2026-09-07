"""平台計價設定（單列）— Issue #74

專案沒有既有的全域單列 platform_settings 表（abuse_settings 是 scope 多列），
故新開 `billing_settings` 單列表：`usd_per_point`（1 點 = X USD，待決 Q4 預設 0.001）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

BILLING_SETTINGS_ID = "default"
DEFAULT_USD_PER_POINT = Decimal("0.001")


@dataclass
class BillingSettings:
    id: str = BILLING_SETTINGS_ID
    usd_per_point: Decimal = field(default_factory=lambda: DEFAULT_USD_PER_POINT)
    updated_by: str | None = None
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def validate(self) -> None:
        if self.usd_per_point <= 0:
            raise ValueError("usd_per_point must be > 0")


class BillingSettingsRepository(ABC):
    @abstractmethod
    async def get(self) -> BillingSettings | None: ...

    @abstractmethod
    async def save(self, settings: BillingSettings) -> None: ...
