"""List Recalc History Use Case — S-Pricing.1"""

from __future__ import annotations

from src.domain.pricing.entity import PricingRecalcAudit
from src.domain.pricing.repository import PricingRecalcAuditRepository


class ListRecalcHistoryUseCase:
    def __init__(self, repo: PricingRecalcAuditRepository) -> None:
        self._repo = repo

    async def execute(self, *, limit: int = 100) -> list[PricingRecalcAudit]:
        return await self._repo.list_recent(limit=limit)
