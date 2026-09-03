from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.auth.api_key import ApiKey


class ApiKeyRepository(ABC):
    @abstractmethod
    async def save(self, key: ApiKey) -> None: ...

    @abstractmethod
    async def find_by_id(self, key_id: str) -> ApiKey | None: ...

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str) -> list[ApiKey]: ...

    @abstractmethod
    async def list_all(self) -> list[ApiKey]: ...

    @abstractmethod
    async def touch_last_used(self, key_id: str, when: datetime) -> None: ...
