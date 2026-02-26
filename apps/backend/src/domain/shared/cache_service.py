"""CacheService ABC — 跨 Bounded Context 共用的快取介面"""

from abc import ABC, abstractmethod


class CacheService(ABC):
    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def set(
        self, key: str, value: str, ttl_seconds: int | None = None
    ) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...
