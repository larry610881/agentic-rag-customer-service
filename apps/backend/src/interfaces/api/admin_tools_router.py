"""Admin API for built-in tool scope management (system_admin only)."""

from __future__ import annotations

import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.container import Container
from src.interfaces.api.deps import CurrentTenant, require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/tools",
    tags=["admin-tools"],
)


class BuiltInToolAdminResponse(BaseModel):
    name: str
    label: str
    description: str
    requires_kb: bool
    scope: str
    tenant_ids: list[str] = Field(default_factory=list)


class UpdateToolScopeRequest(BaseModel):
    scope: str = Field(..., description="'global' or 'tenant'")
    tenant_ids: list[str] = Field(default_factory=list)


@router.get("", response_model=list[BuiltInToolAdminResponse])
@inject
async def list_all_tools(
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case=Depends(Provide[Container.list_built_in_tools_use_case]),
) -> list[BuiltInToolAdminResponse]:
    """系統管理員：列出所有 built-in tool（含 scope + 白名單）。"""
    tools = await use_case.execute(tenant_id=None, is_admin=True)
    return [
        BuiltInToolAdminResponse(
            name=t.name,
            label=t.label,
            description=t.description,
            requires_kb=t.requires_kb,
            scope=t.scope,
            tenant_ids=list(t.tenant_ids),
        )
        for t in tools
    ]


@router.put("/{name}", response_model=BuiltInToolAdminResponse)
@inject
async def update_tool_scope(
    name: str,
    body: UpdateToolScopeRequest,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case=Depends(Provide[Container.update_built_in_tool_scope_use_case]),
    redis_client=Depends(Provide[Container.redis_client]),
) -> BuiltInToolAdminResponse:
    """系統管理員：切換 scope + 設定白名單。"""
    try:
        tool = await use_case.execute(
            name=name,
            scope=body.scope,
            tenant_ids=body.tenant_ids,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Invalidate bot caches so new scope takes effect on next chat request
    try:
        async for key in redis_client.scan_iter(match="bot:*"):
            await redis_client.delete(key)
    except Exception:
        logger.warning("built_in_tool.cache_invalidation.failed", exc_info=True)

    return BuiltInToolAdminResponse(
        name=tool.name,
        label=tool.label,
        description=tool.description,
        requires_kb=tool.requires_kb,
        scope=tool.scope,
        tenant_ids=list(tool.tenant_ids),
    )
