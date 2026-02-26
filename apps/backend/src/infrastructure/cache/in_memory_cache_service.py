"""InMemoryCacheService — 測試用實作，支援 TTL"""

import time

from src.domain.shared.cache_service import CacheService


class InMemoryCacheService(CacheService):
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(
        self, key: str, value: str, ttl_seconds: int | None = None
    ) -> None:
        expires_at = (
            time.monotonic() + ttl_seconds if ttl_seconds is not None else None
        )
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
