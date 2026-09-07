"""點數換算純函式 — Issue #74

規則（Larry 09-07 定案）：
1. token 永遠是事實來源，點數在記帳當下依租戶方案換算，寫進 usage_records.points。
2. 優先用模型點數表（model_pricing.points_per_1k_*）；沒有時用
   `ceil(cost_usd / usd_per_point)` 由美元換算（匯率為平台 billing_settings）。
3. 再乘類別倍率（方案倍率表；未列類別用方案預設倍率），**無條件進位**。
4. 倍率 0 → 0 點（token 紀錄仍存在）。token 制方案永遠 0 點。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Mapping, Protocol

from src.domain.plan.entity import Plan


class UsageLike(Protocol):
    request_type: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    estimated_cost: float


@dataclass(frozen=True)
class ModelPoints:
    """模型點數表（每千 token）。輸入側含 cache read / creation tokens。"""

    points_per_1k_input: Decimal
    points_per_1k_output: Decimal


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def multiplier_for(
    plan: Plan, multipliers: Mapping[str, Decimal], category: str
) -> Decimal:
    value = multipliers.get(category)
    if value is not None:
        return Decimal(value)
    return Decimal(plan.default_category_multiplier)


def points_for(
    usage: UsageLike,
    plan: Plan | None,
    multipliers: Mapping[str, Decimal],
    model_points: ModelPoints | None,
    usd_per_point: Decimal,
) -> int:
    """回傳本筆用量應扣的點數（>= 0）。"""
    if plan is None or not plan.is_points_mode:
        return 0

    multiplier = multiplier_for(plan, multipliers, usage.request_type)
    if multiplier <= 0:
        return 0

    if model_points is not None:
        input_side = (
            usage.input_tokens
            + usage.cache_read_tokens
            + usage.cache_creation_tokens
        )
        base = (
            Decimal(input_side) * model_points.points_per_1k_input
            + Decimal(usage.output_tokens) * model_points.points_per_1k_output
        ) / Decimal(1000)
    else:
        rate = Decimal(usd_per_point)
        if rate <= 0:
            return 0
        base = Decimal(str(usage.estimated_cost)) / rate

    if base <= 0:
        return 0
    return _ceil(Decimal(_ceil(base)) * multiplier)
