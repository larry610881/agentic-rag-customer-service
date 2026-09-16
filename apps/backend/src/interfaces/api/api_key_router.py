"""租戶 API key 管理端點（Issue #67 P2）

tenant_admin 只能操作自己租戶；system_admin 可跨租戶（body / query 指定 tenant_id）。
secret 只在建立回應出現一次。
"""

from datetime import datetime
from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.application.auth.api_key_use_cases import (
    CreateApiKeyCommand,
    CreateApiKeyUseCase,
    ListApiKeysUseCase,
    RevokeApiKeyUseCase,
)
from src.application.shared.idempotency_guard import IdempotencyGuard
from src.container import Container
from src.domain.auth.api_key import API_SCOPES, ApiKey
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.interfaces.api.deps import CurrentTenant, require_role
from src.interfaces.api.errors import ApiError, not_found_code
from src.interfaces.api.idempotency import (
    get_idempotency_key,
    idempotency_scope,
    request_fingerprint,
    run_idempotent,
)
from src.interfaces.api.types import ApiDateTime

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])

_MANAGERS = ("tenant_admin", "system_admin")


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    scopes: list[str]
    allowed_bot_ids: list[str] = []
    expires_at: datetime | None = None
    tenant_id: str | None = None  # 只有 system_admin 可指定


class ApiKeyResponse(BaseModel):
    id: str
    client_id: str
    tenant_id: str
    name: str
    description: str
    secret_prefix: str
    scopes: list[str]
    allowed_bot_ids: list[str]
    expires_at: ApiDateTime | None
    revoked_at: ApiDateTime | None
    is_active: bool
    last_used_at: ApiDateTime | None
    created_by: str | None
    created_at: ApiDateTime


class ApiKeyCreatedResponse(ApiKeyResponse):
    client_secret: str


def _to_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        client_id=key.id,
        tenant_id=key.tenant_id,
        name=key.name,
        description=key.description,
        secret_prefix=key.secret_prefix,
        scopes=list(key.scopes),
        allowed_bot_ids=list(key.allowed_bot_ids),
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        is_active=key.is_active(),
        last_used_at=key.last_used_at,
        created_by=key.created_by,
        created_at=key.created_at,
    )


def _target_tenant(caller: CurrentTenant, requested: str | None) -> str:
    if caller.role == "system_admin":
        if not requested:
            raise ApiError(
                422,
                code="tenant_id_required",
                message="system_admin must specify tenant_id",
            )
        return requested
    if requested and requested != caller.tenant_id:
        raise ApiError(
                403,
                code="cross_tenant_forbidden",
                message="Cannot manage API keys of another tenant",
            )
    return caller.tenant_id


@router.get("/scopes", response_model=list[str])
async def list_scopes(
    _caller: CurrentTenant = Depends(require_role(*_MANAGERS)),
) -> list[str]:
    return sorted(API_SCOPES)


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
@inject
async def create_api_key(
    body: CreateApiKeyRequest,
    caller: CurrentTenant = Depends(require_role(*_MANAGERS)),
    use_case: CreateApiKeyUseCase = Depends(
        Provide[Container.create_api_key_use_case]
    ),
    idempotency_key: str | None = Depends(get_idempotency_key),
    idempotency_guard: IdempotencyGuard | None = Depends(
        Provide[Container.idempotency_guard]
    ),
) -> Any:
    # Issue #98：帶 Idempotency-Key 時「執行一次或重播」；沒帶則行為與過去相同
    return await run_idempotent(
        idempotency_guard,
        key=idempotency_key,
        scope=idempotency_scope(caller, "api_keys.create"),
        fingerprint=request_fingerprint(body),
        handler=lambda: _create_api_key_once(body, caller, use_case),
        status_code=201,
    )


async def _create_api_key_once(
    body: CreateApiKeyRequest,
    caller: CurrentTenant,
    use_case: CreateApiKeyUseCase,
) -> ApiKeyCreatedResponse:
    tenant_id = _target_tenant(caller, body.tenant_id)
    try:
        result = await use_case.execute(
            CreateApiKeyCommand(
                tenant_id=tenant_id,
                name=body.name,
                description=body.description,
                scopes=body.scopes,
                allowed_bot_ids=body.allowed_bot_ids,
                expires_at=body.expires_at,
                actor_user_id=caller.user_id,
            )
        )
    except ValidationError as e:
        raise ApiError(
                422,
                code="invalid_request",
                message=e.message,
            ) from None
    base = _to_response(result.key)
    return ApiKeyCreatedResponse(
        **base.model_dump(), client_secret=result.client_secret
    )
@router.get("", response_model=list[ApiKeyResponse])
@inject
async def list_api_keys(
    tenant_id: str | None = Query(default=None),
    caller: CurrentTenant = Depends(require_role(*_MANAGERS)),
    use_case: ListApiKeysUseCase = Depends(
        Provide[Container.list_api_keys_use_case]
    ),
) -> list[ApiKeyResponse]:
    if caller.role == "system_admin":
        scope_tenant = tenant_id  # None = 全部
    else:
        scope_tenant = _target_tenant(caller, tenant_id)
    keys = await use_case.execute(scope_tenant)
    return [_to_response(k) for k in keys]


@router.delete("/{key_id}", response_model=ApiKeyResponse)
@inject
async def revoke_api_key(
    key_id: str,
    caller: CurrentTenant = Depends(require_role(*_MANAGERS)),
    use_case: RevokeApiKeyUseCase = Depends(
        Provide[Container.revoke_api_key_use_case]
    ),
) -> ApiKeyResponse:
    tenant_scope = None if caller.role == "system_admin" else caller.tenant_id
    try:
        key = await use_case.execute(
            key_id, tenant_id=tenant_scope, actor_user_id=caller.user_id
        )
    except EntityNotFoundError as e:
        raise ApiError(
                404,
                code=not_found_code(e),
                message=e.message,
            ) from None
    return _to_response(key)
