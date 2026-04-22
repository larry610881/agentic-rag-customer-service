"""Deactivate Pricing Use Case — S-Pricing.1

停用某 pricing 版本：把 effective_to 設為 NOW()。
之後該 (provider, model_id) 沒有新版本時，PricingCache miss →
RecordUsageUseCase fallback 到 DEFAULT_MODELS。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog

from src.domain.pricing.repository import ModelPricingRepository

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DeactivatePricingCommand:
    pricing_id: str
    actor: str


class DeactivatePricingUseCase:
    def __init__(self, repo: ModelPricingRepository) -> None:
        self._repo = repo

    async def execute(self, command: DeactivatePricingCommand) -> None:
        pricing = await self._repo.find_by_id(command.pricing_id)
        if pricing is None:
            raise ValueError(f"pricing {command.pricing_id} not found")
        if pricing.effective_to is not None:
            raise ValueError(f"pricing {command.pricing_id} already deactivated")

        now = datetime.now(timezone.utc)
        await self._repo.update_effective_to(
            pricing_id=command.pricing_id, effective_to=now
        )

        logger.info(
            "pricing.deactivate",
            pricing_id=command.pricing_id,
            effective_to=now.isoformat(),
            actor=command.actor,
        )
