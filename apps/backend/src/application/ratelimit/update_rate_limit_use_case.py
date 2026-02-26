from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.ratelimit.entity import RateLimitConfig
from src.domain.ratelimit.repository import RateLimitConfigRepository
from src.domain.ratelimit.value_objects import EndpointGroup, RateLimitConfigId
from src.domain.shared.exceptions import DomainException


class InsufficientPermissionError(DomainException):
    def __init__(self) -> None:
        super().__init__("Only system_admin can manage rate limit configs")


@dataclass(frozen=True)
class UpdateRateLimitCommand:
    tenant_id: str
    endpoint_group: str
    requests_per_minute: int
    burst_size: int
    per_user_requests_per_minute: int | None = None
    caller_role: str = ""


class UpdateRateLimitUseCase:
    def __init__(
        self, rate_limit_config_repository: RateLimitConfigRepository
    ) -> None:
        self._repo = rate_limit_config_repository

    async def execute(self, command: UpdateRateLimitCommand) -> RateLimitConfig:
        if command.caller_role != "system_admin":
            raise InsufficientPermissionError()

        existing = await self._repo.find_by_tenant_and_group(
            command.tenant_id, command.endpoint_group
        )

        if existing:
            existing.requests_per_minute = command.requests_per_minute
            existing.burst_size = command.burst_size
            existing.per_user_requests_per_minute = (
                command.per_user_requests_per_minute
            )
            existing.updated_at = datetime.now(timezone.utc)
            await self._repo.save(existing)
            return existing

        config = RateLimitConfig(
            id=RateLimitConfigId(),
            tenant_id=command.tenant_id,
            endpoint_group=EndpointGroup(command.endpoint_group),
            requests_per_minute=command.requests_per_minute,
            burst_size=command.burst_size,
            per_user_requests_per_minute=command.per_user_requests_per_minute,
        )
        await self._repo.save(config)
        return config
