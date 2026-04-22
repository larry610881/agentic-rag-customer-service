"""Execute Recalculate Use Case — S-Pricing.1

驗 dry_run_token、再跑一次 find_for_recalc 並跟 token snapshot 比對 checksum
（count + cost_before_total）。不一致 → race → abort。
一致 → 交易內 UPDATE token_usage_records + INSERT pricing_recalc_audit。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isclose

import structlog

from src.domain.pricing.entity import ModelPricing, PricingRecalcAudit
from src.domain.pricing.repository import (
    ModelPricingRepository,
    PricingRecalcAuditRepository,
    UsageRecalcPort,
    UsageRecalcRow,
)
from src.domain.rag.pricing import calculate_usage
from src.domain.shared.cache_service import CacheService

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ExecuteRecalculateCommand:
    dry_run_token: str
    reason: str
    actor: str


@dataclass(frozen=True)
class ExecuteRecalculateResult:
    audit_id: str
    affected_rows: int
    cost_before_total: float
    cost_after_total: float


class ExecuteRecalculateUseCase:
    def __init__(
        self,
        pricing_repo: ModelPricingRepository,
        audit_repo: PricingRecalcAuditRepository,
        usage_port: UsageRecalcPort,
        cache: CacheService,
    ) -> None:
        self._pricing_repo = pricing_repo
        self._audit_repo = audit_repo
        self._usage = usage_port
        self._cache = cache

    async def execute(
        self, command: ExecuteRecalculateCommand
    ) -> ExecuteRecalculateResult:
        if not command.dry_run_token:
            raise PermissionError("dry_run_token required")
        if not command.reason or not command.reason.strip():
            raise ValueError("reason is required")

        raw = await self._cache.get(_token_key(command.dry_run_token))
        if raw is None:
            raise PermissionError(
                "dry_run_token expired or not found. "
                "Please re-run dry-run before executing."
            )

        snapshot = json.loads(raw)
        pricing = await self._pricing_repo.find_by_id(snapshot["pricing_id"])
        if pricing is None:
            raise ValueError(f"pricing {snapshot['pricing_id']} not found")

        recalc_from = datetime.fromisoformat(snapshot["recalc_from"])
        recalc_to = datetime.fromisoformat(snapshot["recalc_to"])
        expected_rows = snapshot["affected_rows"]
        expected_cost_before = snapshot["cost_before_total"]

        # 再查一次，跟 snapshot 比對（race detection）
        rows = await self._usage.find_for_recalc(
            provider=pricing.provider,
            model_id=pricing.model_id,
            recalc_from=recalc_from,
            recalc_to=recalc_to,
            limit=expected_rows + 1000,
        )
        if len(rows) != expected_rows:
            raise RuntimeError(
                f"race detected: dry-run saw {expected_rows} rows, "
                f"but execute now sees {len(rows)}. Please re-run dry-run."
            )
        current_cost_before = sum(r.estimated_cost for r in rows)
        if not isclose(current_cost_before, expected_cost_before, rel_tol=1e-9):
            raise RuntimeError(
                f"race detected: cost_before drifted "
                f"({expected_cost_before} → {current_cost_before}). "
                f"Some rows changed since dry-run."
            )

        new_costs = _compute_new_costs(rows, pricing)
        cost_after_total = sum(cost for _, cost in new_costs)
        now = datetime.now(timezone.utc)

        await self._usage.bulk_update_cost(updates=new_costs, recalc_at=now)

        audit = PricingRecalcAudit(
            pricing_id=pricing.id,
            recalc_from=recalc_from,
            recalc_to=recalc_to,
            affected_rows=len(rows),
            cost_before_total=current_cost_before,
            cost_after_total=cost_after_total,
            executed_by=command.actor,
            executed_at=now,
            reason=command.reason,
        )
        await self._audit_repo.save(audit)

        await self._cache.delete(_token_key(command.dry_run_token))

        logger.info(
            "pricing.recalculate.execute",
            audit_id=audit.id,
            pricing_id=pricing.id,
            range_from=recalc_from.isoformat(),
            range_to=recalc_to.isoformat(),
            affected_rows=len(rows),
            cost_before=current_cost_before,
            cost_after=cost_after_total,
            cost_delta=cost_after_total - current_cost_before,
            reason=command.reason,
            actor=command.actor,
        )
        return ExecuteRecalculateResult(
            audit_id=audit.id,
            affected_rows=len(rows),
            cost_before_total=current_cost_before,
            cost_after_total=cost_after_total,
        )


def _token_key(token: str) -> str:
    return f"pricing:recalc:dryrun:{token}"


def _compute_new_costs(
    rows: list[UsageRecalcRow], pricing: ModelPricing
) -> list[tuple[str, float]]:
    pricing_dict = {pricing.model_id: pricing.rate.as_calculate_usage_dict()}
    out: list[tuple[str, float]] = []
    for r in rows:
        usage = calculate_usage(
            model=pricing.model_id,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            pricing=pricing_dict,
            cache_read_tokens=r.cache_read_tokens,
            cache_creation_tokens=r.cache_creation_tokens,
        )
        out.append((r.id, usage.estimated_cost))
    return out
