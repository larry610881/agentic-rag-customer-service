"""Admin API for cross-tenant Knowledge Base overview (system_admin only).

一般租戶視角列表在 /api/v1/knowledge-bases（見 knowledge_base_router.py）。
本 router 提供跨租戶治理視圖，對應前端「系統管理 → 所有知識庫」頁面。
S-Gov.3 決策：職責邊界清楚，不靠 query param 混合兩種視角。
"""

from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.application.knowledge.list_all_knowledge_bases_use_case import (
    ListAllKnowledgeBasesUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, require_role
from src.interfaces.api.knowledge_base_router import (
    KnowledgeBaseResponse,
    _kb_to_response,
)
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

router = APIRouter(
    prefix="/api/v1/admin/knowledge-bases",
    tags=["admin-knowledge-bases"],
)


@router.get("", response_model=PaginatedResponse[KnowledgeBaseResponse])
@inject
async def list_all_knowledge_bases(
    tenant_id: str | None = Query(default=None, description="可選的租戶過濾"),
    pagination: PaginationQuery = Depends(),
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListAllKnowledgeBasesUseCase = Depends(
        Provide[Container.list_all_knowledge_bases_use_case]
    ),
) -> PaginatedResponse[KnowledgeBaseResponse]:
    """系統管理員跨租戶列出所有 KB。可選 tenant_id 過濾特定租戶。"""
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size
    kbs = await use_case.execute(
        tenant_id=tenant_id, limit=limit, offset=offset,
    )
    total = await use_case.count(tenant_id=tenant_id)
    from math import ceil
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[_kb_to_response(kb) for kb in kbs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )
