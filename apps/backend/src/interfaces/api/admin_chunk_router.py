"""Admin Chunk Router — S-KB-Studio.1

Chunk CRUD + retrieval playground + quality summary endpoints for KB Studio.
所有 endpoint 走 tenant chain 驗證（chunk→doc→kb→tenant_id），跨租戶 → 404。
"""

from __future__ import annotations

import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.application.knowledge.delete_chunk_use_case import (
    DeleteChunkCommand,
    DeleteChunkUseCase,
)
from src.application.knowledge.get_kb_quality_summary_use_case import (
    GetKbQualitySummaryQuery,
    GetKbQualitySummaryUseCase,
)
from src.application.knowledge.list_kb_chunks_use_case import (
    ListKbChunksQuery,
    ListKbChunksUseCase,
)
from src.application.knowledge.test_retrieval_use_case import (
    TestRetrievalCommand,
    TestRetrievalUseCase,
)
from src.application.knowledge.update_chunk_use_case import (
    UpdateChunkCommand,
    UpdateChunkUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import DomainException, EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-kb-studio"])


# ---------- Schemas ----------


class ChunkResponse(BaseModel):
    id: str
    document_id: str
    tenant_id: str
    content: str
    context_text: str
    chunk_index: int
    category_id: str | None
    quality_flag: str | None


class ListChunksResponse(BaseModel):
    items: list[ChunkResponse]
    total: int
    page: int
    page_size: int


class UpdateChunkRequest(BaseModel):
    content: str | None = None
    context_text: str | None = None


class RetrievalTestRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    include_conv_summaries: bool = False
    # Real-RAG 對齊參數（Playground 對齊真實對話流程，差只剩 ReAct 決策層）
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    rerank_enabled: bool = False
    rerank_model: str = ""
    rerank_top_n: int = Field(default=20, ge=1, le=100)
    # Issue #43 — multi-mode retrieval
    # retrieval_modes 為主；舊欄位 query_rewrite_enabled / hyde_enabled 仍兼容
    retrieval_modes: list[str] = Field(default_factory=list)
    query_rewrite_enabled: bool = False
    query_rewrite_model: str = ""
    query_rewrite_extra_hint: str = ""
    hyde_enabled: bool = False
    hyde_model: str = ""
    hyde_extra_hint: str = ""
    bot_id: str = ""  # 提供時 rewrite/hyde 會帶該 bot.bot_prompt 作 context


class RetrievalHitResponse(BaseModel):
    chunk_id: str
    content: str
    score: float
    source: str
    metadata: dict


class RetrievalTestResponse(BaseModel):
    results: list[RetrievalHitResponse]
    filter_expr: str
    query_vector_dim: int
    rewritten_query: str = ""  # Legacy: rewrite mode 改寫後字串
    # Issue #43 — 每個 retrieval mode 實際送 embed 的 query 字串
    mode_queries: dict[str, str] = Field(default_factory=dict)


class KbQualitySummaryResponse(BaseModel):
    total_chunks: int
    low_quality_count: int
    avg_cohesion_score: float


# ---------- Helpers ----------


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, EntityNotFoundError):
        # 404 防枚舉（跨租戶訪問不屬於自己的資源 → 404 不 403）
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    if isinstance(exc, DomainException):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="internal error"
    )


def _chunk_dict(chunk) -> ChunkResponse:
    return ChunkResponse(
        id=chunk.id.value if hasattr(chunk.id, "value") else chunk.id,
        document_id=chunk.document_id,
        tenant_id=chunk.tenant_id,
        content=chunk.content,
        context_text=chunk.context_text,
        chunk_index=chunk.chunk_index,
        category_id=chunk.category_id,
        quality_flag=chunk.quality_flag,
    )


# ---------- Endpoints ----------


@router.get(
    "/knowledge-bases/{kb_id}/chunks",
    response_model=ListChunksResponse,
)
@inject
async def list_kb_chunks(
    kb_id: str,
    page: int = 1,
    page_size: int = 50,
    category_id: str | None = None,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListKbChunksUseCase = Depends(
        Provide[Container.list_kb_chunks_use_case]
    ),
) -> ListChunksResponse:
    try:
        result = await use_case.execute(
            ListKbChunksQuery(
                kb_id=kb_id,
                tenant_id=tenant.tenant_id,
                page=page,
                page_size=page_size,
                category_id=category_id,
            )
        )
    except Exception as e:
        raise _map_error(e) from e
    return ListChunksResponse(
        items=[_chunk_dict(c) for c in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.patch("/documents/{doc_id}/chunks/{chunk_id}")
@inject
async def update_chunk(
    doc_id: str,
    chunk_id: str,
    body: UpdateChunkRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: UpdateChunkUseCase = Depends(
        Provide[Container.update_chunk_use_case]
    ),
) -> dict:
    try:
        await use_case.execute(
            UpdateChunkCommand(
                chunk_id=chunk_id,
                tenant_id=tenant.tenant_id,
                content=body.content,
                context_text=body.context_text,
                actor=tenant.user_id or tenant.tenant_id or "",
            )
        )
    except Exception as e:
        raise _map_error(e) from e
    return {"status": "ok", "chunk_id": chunk_id, "reembed_enqueued": True}


@router.post("/chunks/{chunk_id}/re-embed")
async def re_embed_chunk(
    chunk_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
) -> dict:
    # 攻擊面：API 這層只 enqueue，worker 端 use case 第一行 chunk→doc→kb→tenant
    # 驗證才是 authoritative check。任何 tenant 都能 enqueue 但 worker 會驗，
    # 不屬於 caller tenant 的會 silently log warning。
    from src.infrastructure.queue.arq_pool import enqueue
    job_id = await enqueue("reembed_chunk", chunk_id)
    return {"status": "enqueued", "chunk_id": chunk_id, "job_id": job_id}


@router.delete(
    "/chunks/{chunk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def delete_chunk_endpoint(
    chunk_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: DeleteChunkUseCase = Depends(
        Provide[Container.delete_chunk_use_case]
    ),
) -> None:
    try:
        await use_case.execute(
            DeleteChunkCommand(
                chunk_id=chunk_id,
                tenant_id=tenant.tenant_id,
                actor=tenant.user_id or tenant.tenant_id or "",
            )
        )
    except Exception as e:
        raise _map_error(e) from e


@router.post(
    "/knowledge-bases/{kb_id}/retrieval-test",
    response_model=RetrievalTestResponse,
)
@inject
async def retrieval_test(
    kb_id: str,
    body: RetrievalTestRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: TestRetrievalUseCase = Depends(
        Provide[Container.test_retrieval_use_case]
    ),
) -> RetrievalTestResponse:
    try:
        result = await use_case.execute(
            TestRetrievalCommand(
                kb_id=kb_id,
                tenant_id=tenant.tenant_id,
                query=body.query,
                top_k=body.top_k,
                include_conv_summaries=body.include_conv_summaries,
                actor=tenant.user_id or tenant.tenant_id or "",
                score_threshold=body.score_threshold,
                rerank_enabled=body.rerank_enabled,
                rerank_model=body.rerank_model,
                rerank_top_n=body.rerank_top_n,
                retrieval_modes=list(body.retrieval_modes),
                query_rewrite_enabled=body.query_rewrite_enabled,
                query_rewrite_model=body.query_rewrite_model,
                query_rewrite_extra_hint=body.query_rewrite_extra_hint,
                hyde_enabled=body.hyde_enabled,
                hyde_model=body.hyde_model,
                hyde_extra_hint=body.hyde_extra_hint,
                bot_id=body.bot_id,
            )
        )
    except Exception as e:
        raise _map_error(e) from e
    return RetrievalTestResponse(
        results=[
            RetrievalHitResponse(
                chunk_id=h.chunk_id,
                content=h.content,
                score=h.score,
                source=h.source,
                metadata=h.metadata,
            )
            for h in result.results
        ],
        filter_expr=result.filter_expr,
        query_vector_dim=result.query_vector_dim,
        rewritten_query=result.rewritten_query,
        mode_queries=result.mode_queries,
    )


@router.get(
    "/knowledge-bases/{kb_id}/quality-summary",
    response_model=KbQualitySummaryResponse,
)
@inject
async def get_quality_summary(
    kb_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetKbQualitySummaryUseCase = Depends(
        Provide[Container.get_kb_quality_summary_use_case]
    ),
) -> KbQualitySummaryResponse:
    try:
        result = await use_case.execute(
            GetKbQualitySummaryQuery(
                kb_id=kb_id, tenant_id=tenant.tenant_id
            )
        )
    except Exception as e:
        raise _map_error(e) from e
    return KbQualitySummaryResponse(
        total_chunks=result.total_chunks,
        low_quality_count=result.low_quality_count,
        avg_cohesion_score=result.avg_cohesion_score,
    )
