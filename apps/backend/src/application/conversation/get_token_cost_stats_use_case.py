"""Token 成本統計用例"""

from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import ModelCostStat


class GetTokenCostStatsUseCase:
    def __init__(self, usage_repository: UsageRepository) -> None:
        self._usage_repo = usage_repository

    async def execute(
        self, tenant_id: str, days: int = 30
    ) -> list[ModelCostStat]:
        return await self._usage_repo.get_model_cost_stats(tenant_id, days)
