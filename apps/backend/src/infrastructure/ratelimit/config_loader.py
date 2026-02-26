import json
import logging
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from src.domain.ratelimit.repository import RateLimitConfigRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedRateLimitConfig:
    requests_per_minute: int
    burst_size: int
    per_user_requests_per_minute: int | None


# Hardcoded fallbacks if DB and cache both miss
_FALLBACK = ResolvedRateLimitConfig(
    requests_per_minute=200,
    burst_size=250,
    per_user_requests_per_minute=100,
)


class RateLimitConfigLoader:
    def __init__(
        self,
        rate_limit_config_repository: RateLimitConfigRepository,
        redis_client: Redis,
        cache_ttl: int = 60,
    ) -> None:
        self._repo = rate_limit_config_repository
        self._redis = redis_client
        self._cache_ttl = cache_ttl

    async def get_config(
        self, tenant_id: str | None, endpoint_group: str
    ) -> ResolvedRateLimitConfig:
        """Load rate limit config with Redis cache → DB → fallback."""
        cache_key = f"rl_cfg:{tenant_id or 'default'}:{endpoint_group}"

        # Try cache
        try:
            cached = await self._redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return ResolvedRateLimitConfig(**data)
        except (RedisConnectionError, OSError):
            pass

        # Try DB: tenant-specific first, then default
        config = None
        if tenant_id:
            config = await self._repo.find_by_tenant_and_group(
                tenant_id, endpoint_group
            )
        if config is None:
            config = await self._repo.find_by_tenant_and_group(
                None, endpoint_group
            )

        if config is None:
            return _FALLBACK

        resolved = ResolvedRateLimitConfig(
            requests_per_minute=config.requests_per_minute,
            burst_size=config.burst_size,
            per_user_requests_per_minute=config.per_user_requests_per_minute,
        )

        # Cache result
        try:
            await self._redis.setex(
                cache_key,
                self._cache_ttl,
                json.dumps({
                    "requests_per_minute": resolved.requests_per_minute,
                    "burst_size": resolved.burst_size,
                    "per_user_requests_per_minute": (
                        resolved.per_user_requests_per_minute
                    ),
                }),
            )
        except (RedisConnectionError, OSError):
            pass

        return resolved
