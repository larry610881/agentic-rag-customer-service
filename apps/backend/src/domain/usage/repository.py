"""Usage Repository Interface"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.usage.entity import UsageRecord
from src.domain.usage.value_objects import UsageSummary


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
