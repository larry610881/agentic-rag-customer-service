"""Plan 值物件 — Issue #74 類別倍率"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PlanCategoryMultiplier:
    """方案 × 用量類別 → 點數倍率（0 = 該類別不扣點但仍記 token）。"""

    plan_id: str
    usage_category: str
    multiplier: Decimal

    def __post_init__(self) -> None:
        if self.multiplier < 0:
            raise ValueError(
                f"multiplier for {self.usage_category!r} must be >= 0"
            )
