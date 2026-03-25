"""查詢每月 Token 用量趨勢"""

from datetime import datetime

from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import MonthlyUsageStat


class QueryMonthlyUsageUseCase:
    def __init__(self, usage_repository: UsageRepository) -> None:
        self._repo = usage_repository

    async def execute(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[MonthlyUsageStat]:
        return await self._repo.get_monthly_usage_stats(
            tenant_id, start_date, end_date
        )
