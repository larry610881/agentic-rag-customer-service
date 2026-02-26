"""RedisCacheService — Redis 實作，斷線時靜默降級"""

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from src.domain.shared.cache_service import CacheService
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class RedisCacheService(CacheService):
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        try:
            value = await self._redis.get(key)
            if value is None:
                return None
            return value.decode() if isinstance(value, bytes) else value
        except RedisError:
            logger.warning("cache.redis.get_failed", key=key)
            return None

    async def set(
        self, key: str, value: str, ttl_seconds: int | None = None
    ) -> None:
        try:
            if ttl_seconds is not None:
                await self._redis.setex(key, ttl_seconds, value)
            else:
                await self._redis.set(key, value)
        except RedisError:
            logger.warning("cache.redis.set_failed", key=key)

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except RedisError:
            logger.warning("cache.redis.delete_failed", key=key)
