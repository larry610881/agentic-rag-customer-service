"""Dry-Run Recalculate Use Case — S-Pricing.1

回溯重算的預覽路徑：查區間內 usage rows、用目標 pricing 重算成本，
回傳 affected_rows + cost_before/after + 一個 short-lived token。

Token 以 Redis key `pricing:recalc:dryrun:{token}` 存 10min，內容含 checksum
（row count + cost_before_total）供 execute 階段偵測 race。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import structlog

from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.repository import (
    ModelPricingRepository,
    UsageRecalcPort,
)
from src.domain.rag.pricing import calculate_usage
from src.domain.shared.cache_service import CacheService

logger = structlog.get_logger(__name__)

MAX_AFFECTED_ROWS = 100_000
DRY_RUN_TOKEN_TTL_SECONDS = 10 * 60


@dataclass(frozen=True)
class DryRunRecalculateCommand:
    pricing_id: str
    recalc_from: datetime
    recalc_to: datetime
    actor: str


@dataclass(frozen=True)
class DryRunRecalculateResult:
    dry_run_token: str
    pricing_id: str
    affected_rows: int
    cost_before_total: float
    cost_after_total: float
    recalc_from: datetime
    recalc_to: datetime

    @property
    def cost_delta(self) -> float:
        return self.cost_after_total - self.cost_before_total


class DryRunRecalculateUseCase:
    def __init__(
        self,
        pricing_repo: ModelPricingRepository,
        usage_port: UsageRecalcPort,
        cache: CacheService,
    ) -> None:
        self._pricing_repo = pricing_repo
        self._usage = usage_port
        self._cache = cache

    async def execute(
        self, command: DryRunRecalculateCommand
    ) -> DryRunRecalculateResult:
        if command.recalc_from >= command.recalc_to:
            raise ValueError("recalc_from must be earlier than recalc_to")

        pricing = await self._pricing_repo.find_by_id(command.pricing_id)
        if pricing is None:
            raise ValueError(f"pricing {command.pricing_id} not found")

        rows = await self._usage.find_for_recalc(
            provider=pricing.provider,
            model_id=pricing.model_id,
            recalc_from=command.recalc_from,
            recalc_to=command.recalc_to,
            limit=MAX_AFFECTED_ROWS,
        )
        if len(rows) >= MAX_AFFECTED_ROWS:
            raise ValueError(
                f"affected rows exceeds limit ({MAX_AFFECTED_ROWS}). "
                f"請縮小時間區間 recalc_from / recalc_to 後重試"
            )

        cost_before = sum(r.estimated_cost for r in rows)
        cost_after = _recompute_total_cost(rows, pricing)

        token = str(uuid4())
        payload = {
            "pricing_id": pricing.id,
            "recalc_from": command.recalc_from.isoformat(),
            "recalc_to": command.recalc_to.isoformat(),
            "affected_rows": len(rows),
            "cost_before_total": cost_before,
            "cost_after_total": cost_after,
            "actor": command.actor,
        }
        await self._cache.set(
            key=_token_key(token),
            value=json.dumps(payload),
            ttl_seconds=DRY_RUN_TOKEN_TTL_SECONDS,
        )

        logger.info(
            "pricing.recalculate.dry_run",
            pricing_id=pricing.id,
            range_from=command.recalc_from.isoformat(),
            range_to=command.recalc_to.isoformat(),
            affected_rows=len(rows),
            cost_before=cost_before,
            cost_after=cost_after,
            cost_delta=cost_after - cost_before,
            actor=command.actor,
        )

        return DryRunRecalculateResult(
            dry_run_token=token,
            pricing_id=pricing.id,
            affected_rows=len(rows),
            cost_before_total=cost_before,
            cost_after_total=cost_after,
            recalc_from=command.recalc_from,
            recalc_to=command.recalc_to,
        )


def _token_key(token: str) -> str:
    return f"pricing:recalc:dryrun:{token}"


def _recompute_total_cost(
    rows: list, pricing: ModelPricing
) -> float:
    pricing_dict = {pricing.model_id: pricing.rate.as_calculate_usage_dict()}
    total = 0.0
    for r in rows:
        usage = calculate_usage(
            model=pricing.model_id,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            pricing=pricing_dict,
            cache_read_tokens=r.cache_read_tokens,
            cache_creation_tokens=r.cache_creation_tokens,
        )
        total += usage.estimated_cost
    return total
