from abc import ABC, abstractmethod

from src.domain.ratelimit.entity import RateLimitConfig


class RateLimitConfigRepository(ABC):
    @abstractmethod
    async def save(self, config: RateLimitConfig) -> None: ...

    @abstractmethod
    async def find_by_tenant_and_group(
        self, tenant_id: str | None, endpoint_group: str
    ) -> RateLimitConfig | None: ...

    @abstractmethod
    async def find_defaults(self) -> list[RateLimitConfig]: ...

    @abstractmethod
    async def find_all_by_tenant(self, tenant_id: str) -> list[RateLimitConfig]: ...

    @abstractmethod
    async def delete(self, config_id: str) -> None: ...
