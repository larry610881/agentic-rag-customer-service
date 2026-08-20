"""Bot 設定版本 API 端點（spec §8 / §13）

版本狀態機的 HTTP 介面：create / list / get / publish / reject / rollback。
InvalidVersionTransitionError → 409；StaticCheckFailedError → 400 + 逐項明細。
"""

from datetime import datetime
from math import ceil
from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.application.prompt_gate.static_checks import StaticCheckFailedError
from src.application.prompt_gate.version_use_cases import (
    CreateConfigVersionCommand,
    CreateConfigVersionUseCase,
    GetConfigVersionUseCase,
    ListConfigVersionsUseCase,
    PublishConfigVersionUseCase,
    RejectConfigVersionUseCase,
    RollbackConfigVersionCommand,
    RollbackConfigVersionUseCase,
)
from src.container import Container
from src.domain.prompt_gate.entity import InvalidVersionTransitionError
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.schemas.pagination import PaginatedResponse

router = APIRouter(
    prefix="/api/v1/bots/{bot_id}/config-versions",
    tags=["bot-config-versions"],
)


class CreateVersionRequest(BaseModel):
    changes: dict[str, Any] = Field(
        ..., description="白名單欄位的部分更新（key ∈ SNAPSHOT_FIELDS）"
    )


class RollbackRequest(BaseModel):
    target_version_id: str


class VersionResponse(BaseModel):
    id: str
    bot_id: str
    version_no: int
    status: str
    is_current: bool
    source: str
    source_run_id: str | None
    gate_run_id: str | None
    gate_verdict: str | None
    changed_fields: list[str]
    author_user_id: str | None
    published_at: datetime | None
    created_at: datetime


class VersionDetailResponse(VersionResponse):
    config_snapshot: dict[str, Any]
    snapshot_schema: int


def _to_response(version) -> VersionResponse:
    return VersionResponse(
        id=version.id,
        bot_id=version.bot_id,
        version_no=version.version_no,
        status=version.status,
        is_current=version.is_current,
        source=version.source,
        source_run_id=version.source_run_id,
        gate_run_id=version.gate_run_id,
        gate_verdict=version.gate_verdict,
        changed_fields=version.changed_fields,
        author_user_id=version.author_user_id,
        published_at=version.published_at,
        created_at=version.created_at,
    )


def _to_detail(version) -> VersionDetailResponse:
    return VersionDetailResponse(
        **_to_response(version).model_dump(),
        config_snapshot=version.config_snapshot,
        snapshot_schema=version.snapshot_schema,
    )


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
    if isinstance(exc, InvalidVersionTransitionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    if isinstance(exc, StaticCheckFailedError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "static_checks_failed",
                "violations": [
                    {"type": v.type, "detail": v.detail}
                    for v in exc.violations
                ],
            },
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    raise exc


@router.post(
    "", response_model=VersionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_version(
    bot_id: str,
    request: CreateVersionRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: CreateConfigVersionUseCase = Depends(
        Provide[Container.create_config_version_use_case]
    ),
) -> VersionDetailResponse:
    try:
        version = await use_case.execute(
            CreateConfigVersionCommand(
                tenant_id=tenant.tenant_id,
                bot_id=bot_id,
                changes=request.changes,
                author_user_id=tenant.user_id,
            )
        )
    except (
        EntityNotFoundError, StaticCheckFailedError, ValidationError,
    ) as exc:
        raise _handle(exc) from exc
    return _to_detail(version)


@router.get("", response_model=PaginatedResponse[VersionResponse])
@inject
async def list_versions(
    bot_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListConfigVersionsUseCase = Depends(
        Provide[Container.list_config_versions_use_case]
    ),
) -> PaginatedResponse[VersionResponse]:
    versions, total = await use_case.execute(
        tenant.tenant_id, bot_id,
        status=status_filter,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    total_pages = ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[_to_response(v) for v in versions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{version_id}", response_model=VersionDetailResponse)
@inject
async def get_version(
    bot_id: str,
    version_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetConfigVersionUseCase = Depends(
        Provide[Container.get_config_version_use_case]
    ),
) -> VersionDetailResponse:
    try:
        version = await use_case.execute(tenant.tenant_id, version_id)
    except EntityNotFoundError as exc:
        raise _handle(exc) from exc
    if version.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version does not belong to this bot",
        )
    return _to_detail(version)


@router.post("/{version_id}/publish", response_model=VersionResponse)
@inject
async def publish_version(
    bot_id: str,
    version_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: PublishConfigVersionUseCase = Depends(
        Provide[Container.publish_config_version_use_case]
    ),
) -> VersionResponse:
    try:
        version = await use_case.execute(tenant.tenant_id, version_id)
    except (EntityNotFoundError, InvalidVersionTransitionError) as exc:
        raise _handle(exc) from exc
    return _to_response(version)


@router.post("/{version_id}/reject", response_model=VersionResponse)
@inject
async def reject_version(
    bot_id: str,
    version_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: RejectConfigVersionUseCase = Depends(
        Provide[Container.reject_config_version_use_case]
    ),
) -> VersionResponse:
    try:
        version = await use_case.execute(tenant.tenant_id, version_id)
    except (EntityNotFoundError, InvalidVersionTransitionError) as exc:
        raise _handle(exc) from exc
    return _to_response(version)


@router.post("/rollback", response_model=VersionResponse)
@inject
async def rollback_version(
    bot_id: str,
    request: RollbackRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: RollbackConfigVersionUseCase = Depends(
        Provide[Container.rollback_config_version_use_case]
    ),
) -> VersionResponse:
    try:
        version = await use_case.execute(
            RollbackConfigVersionCommand(
                tenant_id=tenant.tenant_id,
                bot_id=bot_id,
                target_version_id=request.target_version_id,
                author_user_id=tenant.user_id,
            )
        )
    except (EntityNotFoundError, ValidationError) as exc:
        raise _handle(exc) from exc
    return _to_response(version)
