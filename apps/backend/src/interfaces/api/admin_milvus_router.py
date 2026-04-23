"""Admin Milvus Router — S-KB-Studio.1

Milvus dashboard + rebuild index endpoints. Platform admin 看全部，tenant admin
只看自己 KB 對應的 `kb_*` collection。
"""

from __future__ import annotations

import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.milvus.get_collection_stats_use_case import (
    GetCollectionStatsQuery,
    GetCollectionStatsUseCase,
)
from src.application.milvus.list_collections_use_case import (
    ListCollectionsQuery,
    ListCollectionsUseCase,
)
from src.application.milvus.rebuild_index_use_case import (
    RebuildIndexCommand,
    RebuildIndexUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/milvus", tags=["admin-milvus"])


class IndexInfo(BaseModel):
    field: str
    index_type: str


class CollectionInfoResponse(BaseModel):
    name: str
    row_count: int
    indexes: list[IndexInfo]


class CollectionStatsResponse(BaseModel):
    row_count: int
    loaded: bool
    indexes: list[IndexInfo]


@router.get("/collections", response_model=list[CollectionInfoResponse])
@inject
async def list_collections(
    tenant: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    use_case: ListCollectionsUseCase = Depends(
        Provide[Container.list_milvus_collections_use_case]
    ),
) -> list[CollectionInfoResponse]:
    result = await use_case.execute(
        ListCollectionsQuery(
            role=tenant.role or "tenant_admin",
            tenant_id=tenant.tenant_id,
        )
    )
    return [
        CollectionInfoResponse(
            name=c.name,
            row_count=c.row_count,
            indexes=[IndexInfo(**i) for i in c.indexes],
        )
        for c in result
    ]


@router.get(
    "/collections/{name}/stats", response_model=CollectionStatsResponse
)
@inject
async def get_collection_stats(
    name: str,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetCollectionStatsUseCase = Depends(
        Provide[Container.get_collection_stats_use_case]
    ),
) -> CollectionStatsResponse:
    stats = await use_case.execute(GetCollectionStatsQuery(collection_name=name))
    return CollectionStatsResponse(
        row_count=int(stats.get("row_count", 0)),
        loaded=bool(stats.get("loaded", False)),
        indexes=[IndexInfo(**i) for i in stats.get("indexes", [])],
    )


@router.post(
    "/collections/{name}/rebuild-index",
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def rebuild_index(
    name: str,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: RebuildIndexUseCase = Depends(
        Provide[Container.rebuild_index_use_case]
    ),
) -> dict:
    try:
        result = await use_case.execute(
            RebuildIndexCommand(
                collection_name=name,
                actor=admin.user_id or admin.tenant_id or "",
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    return result
