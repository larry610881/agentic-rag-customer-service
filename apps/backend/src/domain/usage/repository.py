"""Usage Repository Interface"""

from abc import ABC, abstractmethod
from datetime import datetime

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
    async def sum_tokens_in_cycle(
        self, tenant_id: str, cycle_year_month: str
    ) -> int:
        """SUM total_tokens for (tenant, YYYY-MM cycle). Return 0 if no records.

        Route B: Token 本月額度 total_used_in_cycle 由此 method 供值，
        讓兩頁（Token 用量 / 本月額度）結構上同一份資料。
        """
        ...
