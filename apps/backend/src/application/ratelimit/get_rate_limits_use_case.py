from src.domain.ratelimit.entity import RateLimitConfig
from src.domain.ratelimit.repository import RateLimitConfigRepository
from src.domain.ratelimit.value_objects import EndpointGroup


class GetRateLimitsUseCase:
    def __init__(
        self, rate_limit_config_repository: RateLimitConfigRepository
    ) -> None:
        self._repo = rate_limit_config_repository

    async def execute(self, tenant_id: str) -> dict[str, RateLimitConfig]:
        """Return merged configs: tenant overrides + global defaults."""
        defaults = await self._repo.find_defaults()
        overrides = await self._repo.find_all_by_tenant(tenant_id)

        result: dict[str, RateLimitConfig] = {}

        # Start with defaults
        for cfg in defaults:
            result[cfg.endpoint_group.value] = cfg

        # Override with tenant-specific
        for cfg in overrides:
            result[cfg.endpoint_group.value] = cfg

        # Fill any missing groups with hardcoded fallback
        for group in EndpointGroup:
            if group.value not in result:
                result[group.value] = RateLimitConfig(
                    endpoint_group=group,
                )

        return result
