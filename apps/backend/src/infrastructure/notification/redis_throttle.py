"""Redis-based notification throttle using SETEX."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.domain.observability.notification import NotificationThrottleService


class RedisNotificationThrottle(NotificationThrottleService):
    """O(1) throttle check via Redis SETEX."""

    KEY_PREFIX = "notif_throttle"

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def is_throttled(self, fingerprint: str, channel_id: str) -> bool:
        key = f"{self.KEY_PREFIX}:{fingerprint}:{channel_id}"
        try:
            return bool(await self._redis.exists(key))
        except RedisError:
            return False  # Redis down -> allow (better to over-notify)

    async def record_sent(
        self, fingerprint: str, channel_id: str, ttl_seconds: int
    ) -> None:
        key = f"{self.KEY_PREFIX}:{fingerprint}:{channel_id}"
        try:
            await self._redis.setex(key, ttl_seconds, "1")
        except RedisError:
            pass  # Silent degradation
