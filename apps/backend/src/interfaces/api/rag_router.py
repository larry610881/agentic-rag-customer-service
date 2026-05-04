"""RAG public-facing search API (Issue #44 Phase 3).

POST /api/v1/rag/search — unified cross-KB / multi-mode search for
external producers and SaaS consumers.
"""

from __future__ import annotations

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.application.rag.unified_search_use_case import (
    UnifiedSearchCommand,
    UnifiedSearchUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


class UnifiedSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    kb_ids: list[str] = Field(..., min_length=1, max_length=20)
    retrieval_modes: list[str] = Field(default_factory=lambda: ["raw"])
    rerank_enabled: bool = False
    rerank_model: str = ""
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    filters: dict[str, Any] = Field(default_factory=dict)


class UnifiedSearchResultBody(BaseModel):
    chunk_id: str
    score: float
    kb_id: str
    content: str
    document_id: str
    document_name: str
    source: str = ""
    source_id: str = ""


class UnifiedSearchResponse(BaseModel):
    results: list[UnifiedSearchResultBody]
    mode_queries: dict[str, str]
    total_after_rerank: int


@router.post("/search", response_model=UnifiedSearchResponse)
@inject
async def unified_search(
    body: UnifiedSearchRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: UnifiedSearchUseCase = Depends(
        Provide[Container.unified_search_use_case]
    ),
) -> UnifiedSearchResponse:
    try:
        result = await use_case.execute(
            UnifiedSearchCommand(
                tenant_id=tenant.tenant_id,
                kb_ids=body.kb_ids,
                query=body.query,
                retrieval_modes=body.retrieval_modes,
                rerank_enabled=body.rerank_enabled,
                rerank_model=body.rerank_model,
                top_k=body.top_k,
                score_threshold=body.score_threshold,
                filters=body.filters,
            )
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None

    return UnifiedSearchResponse(
        results=[
            UnifiedSearchResultBody(
                chunk_id=r.chunk_id,
                score=r.score,
                kb_id=r.kb_id,
                content=r.content,
                document_id=r.document_id,
                document_name=r.document_name,
                source=r.source,
                source_id=r.source_id,
            )
            for r in result.results
        ],
        mode_queries=result.mode_queries,
        total_after_rerank=result.total_after_rerank,
    )
