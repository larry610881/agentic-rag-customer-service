from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.application.ratelimit.get_rate_limits_use_case import GetRateLimitsUseCase
from src.application.ratelimit.update_rate_limit_use_case import (
    UpdateRateLimitCommand,
    UpdateRateLimitUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, require_role

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class RateLimitConfigResponse(BaseModel):
    endpoint_group: str
    requests_per_minute: int
    burst_size: int
    per_user_requests_per_minute: int | None = None
    tenant_id: str | None = None


class UpdateRateLimitRequest(BaseModel):
    endpoint_group: str
    requests_per_minute: int
    burst_size: int
    per_user_requests_per_minute: int | None = None


@router.get(
    "/rate-limits/{tenant_id}",
    response_model=list[RateLimitConfigResponse],
)
@inject
async def get_rate_limits(
    tenant_id: str,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetRateLimitsUseCase = Depends(
        Provide[Container.get_rate_limits_use_case]
    ),
) -> list[RateLimitConfigResponse]:
    """Get merged rate limit configs for a tenant (defaults + overrides)."""
    configs = await use_case.execute(tenant_id)
    return [
        RateLimitConfigResponse(
            endpoint_group=cfg.endpoint_group.value,
            requests_per_minute=cfg.requests_per_minute,
            burst_size=cfg.burst_size,
            per_user_requests_per_minute=cfg.per_user_requests_per_minute,
            tenant_id=cfg.tenant_id,
        )
        for cfg in configs.values()
    ]


@router.put(
    "/rate-limits/{tenant_id}",
    response_model=RateLimitConfigResponse,
)
@inject
async def update_rate_limit(
    tenant_id: str,
    body: UpdateRateLimitRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateRateLimitUseCase = Depends(
        Provide[Container.update_rate_limit_use_case]
    ),
) -> RateLimitConfigResponse:
    """Create or update a rate limit config for a tenant."""
    command = UpdateRateLimitCommand(
        tenant_id=tenant_id,
        endpoint_group=body.endpoint_group,
        requests_per_minute=body.requests_per_minute,
        burst_size=body.burst_size,
        per_user_requests_per_minute=body.per_user_requests_per_minute,
        caller_role=admin.role or "",
    )
    config = await use_case.execute(command)
    return RateLimitConfigResponse(
        endpoint_group=config.endpoint_group.value,
        requests_per_minute=config.requests_per_minute,
        burst_size=config.burst_size,
        per_user_requests_per_minute=config.per_user_requests_per_minute,
        tenant_id=config.tenant_id,
    )
