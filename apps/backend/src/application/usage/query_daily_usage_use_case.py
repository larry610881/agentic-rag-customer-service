"""查詢每日 Token 用量趨勢"""

from datetime import datetime

from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import DailyUsageStat


class QueryDailyUsageUseCase:
    def __init__(self, usage_repository: UsageRepository) -> None:
        self._repo = usage_repository

    async def execute(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DailyUsageStat]:
        return await self._repo.get_daily_usage_stats(tenant_id, start_date, end_date)
