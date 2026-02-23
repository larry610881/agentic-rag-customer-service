"""查詢 Token 使用摘要用例"""

from datetime import datetime

from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import UsageSummary


class QueryUsageUseCase:
    def __init__(self, usage_repository: UsageRepository) -> None:
        self._repo = usage_repository

    async def execute(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> UsageSummary:
        return await self._repo.get_tenant_summary(
            tenant_id, start_date, end_date
        )
