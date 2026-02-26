from src.domain.ratelimit.entity import RateLimitConfig
from src.domain.ratelimit.repository import RateLimitConfigRepository
from src.domain.ratelimit.value_objects import EndpointGroup, RateLimitConfigId

DEFAULT_CONFIGS = [
    {
        "endpoint_group": EndpointGroup.FEEDBACK,
        "requests_per_minute": 30,
        "burst_size": 40,
        "per_user_requests_per_minute": 10,
    },
    {
        "endpoint_group": EndpointGroup.RAG,
        "requests_per_minute": 100,
        "burst_size": 120,
        "per_user_requests_per_minute": 50,
    },
    {
        "endpoint_group": EndpointGroup.GENERAL,
        "requests_per_minute": 200,
        "burst_size": 250,
        "per_user_requests_per_minute": 100,
    },
    {
        "endpoint_group": EndpointGroup.WEBHOOK,
        "requests_per_minute": 60,
        "burst_size": 80,
        "per_user_requests_per_minute": None,
    },
]


class SeedDefaultsUseCase:
    def __init__(
        self, rate_limit_config_repository: RateLimitConfigRepository
    ) -> None:
        self._repo = rate_limit_config_repository

    async def execute(self) -> int:
        """Seed default configs if missing. Returns count created."""
        existing = await self._repo.find_defaults()
        existing_groups = {cfg.endpoint_group for cfg in existing}

        created = 0
        for default in DEFAULT_CONFIGS:
            if default["endpoint_group"] not in existing_groups:
                config = RateLimitConfig(
                    id=RateLimitConfigId(),
                    tenant_id=None,
                    endpoint_group=default["endpoint_group"],
                    requests_per_minute=default["requests_per_minute"],
                    burst_size=default["burst_size"],
                    per_user_requests_per_minute=default[
                        "per_user_requests_per_minute"
                    ],
                )
                await self._repo.save(config)
                created += 1

        return created
