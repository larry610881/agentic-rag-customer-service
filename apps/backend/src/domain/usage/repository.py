"""Usage Repository Interface"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from src.domain.usage.entity import UsageRecord
from src.domain.usage.value_objects import (
    BotUsageStat,
    DailyUsageStat,
    ModelCostStat,
    MonthlyUsageStat,
    UsageSummary,
)


class UsageRepository(ABC):
    @abstractmethod
    async def save(self, record: UsageRecord) -> None: ...

    @abstractmethod
    async def find_by_tenant(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[UsageRecord]: ...

    @abstractmethod
    async def get_tenant_summary(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> UsageSummary: ...

    @abstractmethod
    async def get_model_cost_stats(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[ModelCostStat]: ...

    @abstractmethod
    async def get_bot_usage_stats(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BotUsageStat]: ...

    @abstractmethod
    async def get_daily_usage_stats(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DailyUsageStat]: ...

    @abstractmethod
    async def get_monthly_usage_stats(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[MonthlyUsageStat]: ...

    @abstractmethod
    async def sum_tokens_in_range(
        self, tenant_id: str, start: datetime, end: datetime
    ) -> int:
        """SUM total_tokens for (tenant_id, [start, end) range). Return 0 if no records.

        Token-Gov.6: 唯一的 SUM 入口。本月額度 / Token 用量頁共用這個 SQL path，
        避免兩條 code path drift。實作需 SUM 4 欄加總
        (input + output + cache_read + cache_creation) — 因為 `total_tokens`
        欄位已刪除（Token-Gov.6 migration）。
        """
        ...

    async def sum_tokens_in_cycle(
        self, tenant_id: str, cycle_year_month: str
    ) -> int:
        """SUM total_tokens for (tenant, YYYY-MM cycle). Return 0 if no records.

        Route B: Token 本月額度 total_used_in_cycle 由此 method 供值。
        Token-Gov.6: 改為薄 wrapper，內部 delegate 給 sum_tokens_in_range。
        """
        year, month = cycle_year_month.split("-")
        start = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
        if int(month) == 12:
            end = datetime(int(year) + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(int(year), int(month) + 1, 1, tzinfo=timezone.utc)
        return await self.sum_tokens_in_range(tenant_id, start, end)
