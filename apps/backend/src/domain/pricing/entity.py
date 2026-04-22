"""Pricing 限界上下文實體"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.pricing.value_objects import PriceRate, PricingCategory


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ModelPricing:
    """Append-only pricing 版本。

    規則：
    - `effective_from` 寫入時必須 >= NOW()（by UseCase 檢查）
    - `effective_to` 在建立時為 None；被下一版取代時設為下一版的 effective_from
    - 停用 = 把 `effective_to` 設為 NOW()
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    provider: str = ""
    model_id: str = ""
    display_name: str = ""
    category: PricingCategory = PricingCategory.LLM
    rate: PriceRate = field(default_factory=lambda: PriceRate(0.0, 0.0))
    effective_from: datetime = field(default_factory=_now)
    effective_to: datetime | None = None
    created_by: str = ""
    created_at: datetime = field(default_factory=_now)
    note: str | None = None

    def is_active_at(self, at: datetime) -> bool:
        if at < self.effective_from:
            return False
        if self.effective_to is not None and at >= self.effective_to:
            return False
        return True


@dataclass
class PricingRecalcAudit:
    """回溯重算審計條目（append-only）"""

    id: str = field(default_factory=lambda: str(uuid4()))
    pricing_id: str = ""
    recalc_from: datetime = field(default_factory=_now)
    recalc_to: datetime = field(default_factory=_now)
    affected_rows: int = 0
    cost_before_total: float = 0.0
    cost_after_total: float = 0.0
    executed_by: str = ""
    executed_at: datetime = field(default_factory=_now)
    reason: str = ""

    @property
    def cost_delta(self) -> float:
        return self.cost_after_total - self.cost_before_total
