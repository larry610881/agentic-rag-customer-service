from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.auth.delete_user_use_case import DeleteUserUseCase
from src.application.auth.get_user_use_case import GetUserUseCase
from src.application.auth.list_users_use_case import ListUsersUseCase
from src.application.auth.register_user_use_case import (
    RegisterUserCommand,
    RegisterUserUseCase,
)
from src.application.auth.reset_password_use_case import (
    ResetPasswordCommand,
    ResetPasswordUseCase,
)
from src.application.auth.update_user_use_case import (
    UpdateUserCommand,
    UpdateUserUseCase,
)
from src.application.ratelimit.get_rate_limits_use_case import GetRateLimitsUseCase
from src.application.ratelimit.update_rate_limit_use_case import (
    UpdateRateLimitCommand,
    UpdateRateLimitUseCase,
)
from src.container import Container
from src.domain.auth.entity import InvalidTenantBindingError, TenantRequiredError
from src.domain.shared.exceptions import DuplicateEntityError, EntityNotFoundError
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


# --- User Management ---


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str
    created_at: str
    updated_at: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "user"
    tenant_id: str


class UpdateUserRequest(BaseModel):
    role: str | None = None
    tenant_id: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


def _user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id.value,
        tenant_id=user.tenant_id or "",
        email=user.email.value,
        role=user.role.value,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.get("/users", response_model=list[UserResponse])
@inject
async def list_users(
    tenant_id: str | None = None,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListUsersUseCase = Depends(
        Provide[Container.list_users_use_case]
    ),
) -> list[UserResponse]:
    users = await use_case.execute(tenant_id)
    return [_user_response(u) for u in users]


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_user(
    body: CreateUserRequest,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: RegisterUserUseCase = Depends(
        Provide[Container.register_user_use_case]
    ),
) -> UserResponse:
    try:
        user = await use_case.execute(
            RegisterUserCommand(
                email=body.email,
                password=body.password,
                role=body.role,
                tenant_id=body.tenant_id,
            )
        )
    except DuplicateEntityError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=e.message) from None
    except (InvalidTenantBindingError, TenantRequiredError) as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from None
    return _user_response(user)


@router.get("/users/{user_id}", response_model=UserResponse)
@inject
async def get_user(
    user_id: str,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetUserUseCase = Depends(
        Provide[Container.get_user_use_case]
    ),
) -> UserResponse:
    try:
        user = await use_case.execute(user_id)
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    return _user_response(user)


@router.put("/users/{user_id}", response_model=UserResponse)
@inject
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateUserUseCase = Depends(
        Provide[Container.update_user_use_case]
    ),
) -> UserResponse:
    try:
        user = await use_case.execute(
            UpdateUserCommand(
                user_id=user_id,
                role=body.role,
                tenant_id=body.tenant_id,
            )
        )
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    except (InvalidTenantBindingError, TenantRequiredError) as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from None
    return _user_response(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_user(
    user_id: str,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: DeleteUserUseCase = Depends(
        Provide[Container.delete_user_use_case]
    ),
) -> None:
    try:
        await use_case.execute(user_id)
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


@router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ResetPasswordUseCase = Depends(
        Provide[Container.reset_password_use_case]
    ),
) -> None:
    try:
        await use_case.execute(
            ResetPasswordCommand(
                user_id=user_id,
                new_password=body.new_password,
            )
        )
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
