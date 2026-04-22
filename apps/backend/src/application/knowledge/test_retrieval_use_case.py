"""Test Retrieval Use Case (Playground) — S-KB-Studio.1

薄 wrapper：驗 tenant chain → 呼叫 VectorStore.search 帶 tenant filter
→ 可選合併 conv_summary cross-search → 回傳 results + filter_expr。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.services import EmbeddingService, VectorStore
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class TestRetrievalCommand:
    kb_id: str
    tenant_id: str
    query: str
    top_k: int = 5
    include_conv_summaries: bool = False
    actor: str = ""


@dataclass
class RetrievalHit:
    chunk_id: str
    content: str
    score: float
    source: str = "chunk"  # "chunk" | "conv_summary"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestRetrievalResult:
    results: list[RetrievalHit]
    filter_expr: str
    query_vector_dim: int


class TestRetrievalUseCase:
    def __init__(
        self,
        kb_repo: KnowledgeBaseRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._kb_repo = kb_repo
        self._embed = embedding_service
        self._vs = vector_store

    async def execute(
        self, command: TestRetrievalCommand
    ) -> TestRetrievalResult:
        kb = await self._kb_repo.find_by_id(command.kb_id)
        if kb is None or kb.tenant_id != command.tenant_id:
            raise EntityNotFoundError(f"kb {command.kb_id} not found")
        if not command.query.strip():
            raise ValueError("query must not be empty")

        query_vector = await self._embed.embed_query(command.query)
        filters = {"tenant_id": command.tenant_id}
        filter_expr = f'tenant_id == "{command.tenant_id}"'

        collection = f"kb_{kb.id}"
        chunk_results = await self._vs.search(
            collection=collection,
            query_vector=query_vector,
            limit=command.top_k,
            filters=filters,
        )
        hits: list[RetrievalHit] = [
            RetrievalHit(
                chunk_id=r.id,
                content=(r.payload or {}).get("content", ""),
                score=r.score,
                source="chunk",
                metadata=r.payload or {},
            )
            for r in chunk_results
        ]

        if command.include_conv_summaries:
            conv_results = await self._vs.search(
                collection="conv_summaries",
                query_vector=query_vector,
                limit=command.top_k,
                filters=filters,
            )
            hits.extend(
                RetrievalHit(
                    chunk_id=r.id,
                    content=(r.payload or {}).get("summary", ""),
                    score=r.score,
                    source="conv_summary",
                    metadata=r.payload or {},
                )
                for r in conv_results
            )
            hits.sort(key=lambda h: h.score, reverse=True)

        return TestRetrievalResult(
            results=hits,
            filter_expr=filter_expr,
            query_vector_dim=len(query_vector),
        )
