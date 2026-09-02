import json
import logging
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

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

# Issue #58：auth（login / register / token）沒有 JWT 只能按 IP 計，
# 預設要遠比一般端點嚴——10 rpm 足夠正常登入，暴力嘗試立刻撞牆。
_GROUP_FALLBACKS: dict[str, ResolvedRateLimitConfig] = {
    "auth": ResolvedRateLimitConfig(
        requests_per_minute=10,
        burst_size=10,
        per_user_requests_per_minute=None,
    ),
}


class RateLimitConfigLoader:
    def __init__(
        self,
        rate_limit_config_repo_factory,  # Callable — creates a fresh repo each call
        redis_client: Redis,
        cache_ttl: int = 60,
    ) -> None:
        self._repo_factory = rate_limit_config_repo_factory
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
        repo = self._repo_factory()
        config = None
        if tenant_id:
            config = await repo.find_by_tenant_and_group(
                tenant_id, endpoint_group
            )
        if config is None:
            config = await repo.find_by_tenant_and_group(
                None, endpoint_group
            )

        if config is None:
            return _GROUP_FALLBACKS.get(endpoint_group, _FALLBACK)

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
