"""Create Pricing Use Case — S-Pricing.1

Append-only：新增新版本時，把同 (provider, model_id) 當前生效版本的
`effective_to` 設成新版本的 `effective_from`，保歷史 snapshot 不變。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog

from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.repository import ModelPricingRepository
from src.domain.pricing.value_objects import PriceRate, PricingCategory

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CreatePricingCommand:
    provider: str
    model_id: str
    display_name: str
    input_price: float
    output_price: float
    cache_read_price: float
    cache_creation_price: float
    effective_from: datetime
    note: str
    category: PricingCategory = PricingCategory.LLM
    created_by: str = ""


class CreatePricingUseCase:
    def __init__(self, repo: ModelPricingRepository) -> None:
        self._repo = repo

    async def execute(self, command: CreatePricingCommand) -> ModelPricing:
        now = datetime.now(timezone.utc)
        if command.effective_from < now:
            raise ValueError(
                "effective_from must be >= now. "
                f"Got {command.effective_from.isoformat()}, now={now.isoformat()}"
            )
        if not command.note or not command.note.strip():
            raise ValueError("note is required (describe why the price changed)")
        if not command.provider or not command.model_id:
            raise ValueError("provider and model_id are required")
        if not command.created_by:
            raise ValueError("created_by is required (user email/id snapshot)")

        # 釘死舊版本 effective_to = 新版 effective_from
        existing = await self._repo.find_active_version(
            provider=command.provider,
            model_id=command.model_id,
            at=command.effective_from,
        )
        if existing is not None and existing.effective_to is None:
            await self._repo.update_effective_to(
                pricing_id=existing.id, effective_to=command.effective_from
            )

        rate = PriceRate(
            input_price=command.input_price,
            output_price=command.output_price,
            cache_read_price=command.cache_read_price,
            cache_creation_price=command.cache_creation_price,
        )
        pricing = ModelPricing(
            provider=command.provider,
            model_id=command.model_id,
            display_name=command.display_name or command.model_id,
            category=command.category,
            rate=rate,
            effective_from=command.effective_from,
            created_by=command.created_by,
            note=command.note,
        )
        await self._repo.save(pricing)

        logger.info(
            "pricing.create",
            pricing_id=pricing.id,
            provider=pricing.provider,
            model_id=pricing.model_id,
            effective_from=pricing.effective_from.isoformat(),
            input_price=rate.input_price,
            output_price=rate.output_price,
            actor=command.created_by,
            note=command.note,
        )
        return pricing
