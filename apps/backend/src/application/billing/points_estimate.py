"""估算端點的點數換算 — Issue #74

`/estimate` 類端點在用量發生前估成本（USD）；點數制租戶另回估算點數：
`ceil(est_cost_usd / usd_per_point) × 類別倍率`（無條件進位）。估算階段不查模型
點數表（多模型混用、且是估算），實際記帳仍以 `points_for` 為準。fail-open：
脈絡載入失敗回 token 制 / 0 點。
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import Any

import structlog

from src.domain.plan.entity import BillingMode

logger = structlog.get_logger(__name__)


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


async def estimate_points(
    billing_context: Any | None,
    tenant_id: str,
    category: str,
    est_cost_usd: float,
) -> dict[str, Any]:
    """回 `{"billing_mode": ..., "est_points": int}`（token 制恆 0）。"""
    view: dict[str, Any] = {"billing_mode": BillingMode.TOKEN, "est_points": 0}
    if billing_context is None or not tenant_id:
        return view
    try:
        ctx = await billing_context.for_tenant(tenant_id)
    except Exception:
        logger.warning("points_estimate.context_failed", tenant_id=tenant_id)
        return view
    if ctx is None or ctx.plan is None or not ctx.is_points_mode:
        return view
    multiplier = ctx.multiplier_for(category)
    points = 0
    if multiplier > 0 and est_cost_usd > 0 and ctx.usd_per_point > 0:
        base = _ceil(Decimal(str(est_cost_usd)) / Decimal(ctx.usd_per_point))
        points = _ceil(Decimal(base) * multiplier)
    view.update(billing_mode=BillingMode.POINTS, est_points=points)
    return view
