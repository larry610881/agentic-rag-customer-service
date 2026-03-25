"""按 Bot 查詢 Token 用量"""

from datetime import datetime

from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import BotUsageStat


class QueryBotUsageUseCase:
    def __init__(self, usage_repository: UsageRepository) -> None:
        self._repo = usage_repository

    async def execute(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BotUsageStat]:
        return await self._repo.get_bot_usage_stats(tenant_id, start_date, end_date)
