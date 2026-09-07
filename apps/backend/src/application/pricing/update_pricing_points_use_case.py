"""Update Pricing Points Use Case — Issue #74

model_pricing 的美元價是 append-only；點數表是獨立軸（可直接改），
變更寫稽核並刷新 pricing cache（由 router 呼叫 refresh）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.repository import ModelPricingRepository

AUDIT_ENTITY = "model_pricing"


@dataclass(frozen=True)
class UpdatePricingPointsCommand:
    pricing_id: str
    points_per_1k_input: float | None
    points_per_1k_output: float | None
    actor_user_id: str | None = None


class UpdatePricingPointsUseCase:
    def __init__(self, repo: ModelPricingRepository, audit: Any | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(self, command: UpdatePricingPointsCommand) -> ModelPricing:
        ppi, ppo = command.points_per_1k_input, command.points_per_1k_output
        if (ppi is None) != (ppo is None):
            raise ValueError(
                "points_per_1k_input and points_per_1k_output must be set together"
            )
        if ppi is not None and (ppi < 0 or (ppo is not None and ppo < 0)):
            raise ValueError("points must be >= 0")

        pricing = await self._repo.find_by_id(command.pricing_id)
        if pricing is None:
            raise ValueError(f"pricing {command.pricing_id} not found")

        before = {
            "points_per_1k_input": pricing.points_per_1k_input,
            "points_per_1k_output": pricing.points_per_1k_output,
        }
        await self._repo.update_points(command.pricing_id, ppi, ppo)
        pricing.points_per_1k_input = ppi
        pricing.points_per_1k_output = ppo
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=pricing.id,
                action="update",
                before=before,
                after={"points_per_1k_input": ppi, "points_per_1k_output": ppo},
                actor_user_id=command.actor_user_id,
            )
        return pricing
