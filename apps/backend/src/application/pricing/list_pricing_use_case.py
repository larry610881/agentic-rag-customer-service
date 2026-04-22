"""List Pricing Use Case — S-Pricing.1"""

from __future__ import annotations

from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.repository import ModelPricingRepository


class ListPricingUseCase:
    def __init__(self, repo: ModelPricingRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        provider: str | None = None,
        category: str | None = None,
    ) -> list[ModelPricing]:
        return await self._repo.find_all_versions(
            provider=provider, category=category
        )
