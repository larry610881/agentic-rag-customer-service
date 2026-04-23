"""Admin Conversation Summary Router — S-KB-Studio.1

獨立 admin 頁（/admin/conversation-summary）。list + search 兩 endpoints。
租戶/bot filter 必帶；跨租戶查 bot 回 404。
"""

from __future__ import annotations

import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.application.conversation.list_conv_summaries_use_case import (
    ListConvSummariesQuery,
    ListConvSummariesUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/conv-summaries", tags=["admin-conv-summary"])


class ConvSummaryItem(BaseModel):
    conversation_id: str | None = None
    tenant_id: str
    bot_id: str | None = None
    summary: str | None = None
    created_at: str | None = None


class ListConvSummariesResponse(BaseModel):
    items: list[ConvSummaryItem]


class ConvSummarySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    tenant_id: str
    bot_id: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)


@router.get("", response_model=ListConvSummariesResponse)
@inject
async def list_summaries(
    tenant_id: str,
    bot_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    admin: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    use_case: ListConvSummariesUseCase = Depends(
        Provide[Container.list_conv_summaries_use_case]
    ),
) -> ListConvSummariesResponse:
    # 跨租戶擋：tenant_admin 只能查自己
    if admin.role == "tenant_admin" and admin.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        )
    try:
        items = await use_case.execute(
            ListConvSummariesQuery(
                role=admin.role or "tenant_admin",
                tenant_id=tenant_id,
                bot_id=bot_id,
                page=page,
                page_size=page_size,
            )
        )
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    # 統一 schema
    normalized: list[ConvSummaryItem] = []
    for it in items or []:
        if isinstance(it, dict):
            normalized.append(
                ConvSummaryItem(
                    conversation_id=it.get("conversation_id") or it.get("id"),
                    tenant_id=it.get("tenant_id", tenant_id),
                    bot_id=it.get("bot_id"),
                    summary=it.get("summary"),
                    created_at=(
                        str(it.get("created_at"))
                        if it.get("created_at")
                        else None
                    ),
                )
            )
    return ListConvSummariesResponse(items=normalized)


@router.post("/search")
@inject
async def search_summaries(
    body: ConvSummarySearchRequest,
    admin: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    vector_store=Depends(Provide[Container.vector_store]),
    embedding_service=Depends(Provide[Container.embedding_service]),
) -> dict:
    if admin.role == "tenant_admin" and admin.tenant_id != body.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        )
    # 薄 wrapper：直接呼叫既有 search_conv_summaries
    query_vector = await embedding_service.embed_query(body.query)
    results = await vector_store.search_conv_summaries(
        query_vector=query_vector,
        tenant_id=body.tenant_id,
        bot_id=body.bot_id,
        limit=body.top_k,
    )
    return {
        "results": [
            {
                "id": r.id,
                "score": r.score,
                "summary": (r.payload or {}).get("summary", ""),
                "bot_id": (r.payload or {}).get("bot_id"),
            }
            for r in results
        ]
    }
