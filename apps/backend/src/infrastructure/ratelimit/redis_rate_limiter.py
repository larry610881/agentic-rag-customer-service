import logging
import time

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.domain.ratelimit.rate_limiter_service import (
    RateLimiterService,
    RateLimitResult,
)

logger = logging.getLogger(__name__)


class RedisRateLimiter(RateLimiterService):
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def check_rate_limit(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        try:
            return await self._check(key, limit, window_seconds)
        except (RedisConnectionError, RedisTimeoutError, OSError):
            logger.warning(
                "redis_unavailable_graceful_degradation",
                extra={"key": key},
            )
            return RateLimitResult(allowed=True, remaining=limit)

    async def _check(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

        count = results[2]

        if count > limit:
            # Remove the request we just added since it's over limit
            await self._redis.zrem(key, str(now))
            # Calculate retry_after from oldest entry in window
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            retry_after = 1
            if oldest:
                oldest_time = oldest[0][1]
                retry_after = max(1, int(window_seconds - (now - oldest_time)) + 1)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=retry_after,
            )

        remaining = max(0, limit - count)
        return RateLimitResult(allowed=True, remaining=remaining)
