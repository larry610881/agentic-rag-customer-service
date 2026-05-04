"""Unified Search use case (Issue #44 — External Producer Integration).

Thin wrapper over ``QueryRAGUseCase.retrieve`` that exposes the Milvus
metadata filter (source / source_id / etc.) to external consumers, and
projects the retrieve result into a flat search-response shape (no LLM
generation — pure retrieval).

Compared to ``test_retrieval`` / ``query_rag``, this use case is
positioned as the public producer-facing search API:
- accepts any KB list within the tenant
- accepts any subset of multi-mode retrieval flags
- accepts metadata filter for first-class fields
- response includes per-result kb_id + payload metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.application.rag.query_rag_use_case import (
    QueryRAGCommand,
    QueryRAGUseCase,
)
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.shared.exceptions import (
    EntityNotFoundError,
    NoRelevantKnowledgeError,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class UnifiedSearchCommand:
    tenant_id: str
    kb_ids: list[str]
    query: str
    retrieval_modes: list[str] = field(default_factory=lambda: ["raw"])
    rerank_enabled: bool = False
    rerank_model: str = ""
    top_k: int = 5
    score_threshold: float = 0.3
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedSearchResultItem:
    chunk_id: str
    score: float
    kb_id: str
    content: str
    document_id: str
    document_name: str
    source: str
    source_id: str


@dataclass
class UnifiedSearchResult:
    results: list[UnifiedSearchResultItem]
    mode_queries: dict[str, str]
    total_after_rerank: int


class UnifiedSearchUseCase:
    def __init__(
        self,
        kb_repo: KnowledgeBaseRepository,
        query_rag_use_case: QueryRAGUseCase,
    ) -> None:
        self._kb_repo = kb_repo
        self._query_rag = query_rag_use_case

    async def execute(self, command: UnifiedSearchCommand) -> UnifiedSearchResult:
        if not command.kb_ids:
            raise ValueError("kb_ids must contain at least 1 entry")

        # Validate every KB belongs to the tenant (or system_admin bypass).
        # Uniform 404 if any does not — prevents enumeration of foreign KBs.
        for kid in command.kb_ids:
            await ensure_kb_accessible(self._kb_repo, kid, command.tenant_id)

        rag_command = QueryRAGCommand(
            tenant_id=command.tenant_id,
            kb_id=command.kb_ids[0],
            kb_ids=command.kb_ids,
            query=command.query,
            top_k=command.top_k,
            score_threshold=command.score_threshold,
            retrieval_modes=command.retrieval_modes,
            rerank_enabled=command.rerank_enabled,
            rerank_model=command.rerank_model,
            extra_filters=command.filters or None,
        )

        try:
            retrieve_result = await self._query_rag.retrieve(rag_command)
        except NoRelevantKnowledgeError:
            # No-results path: return empty payload (200) rather than 404 —
            # consumer treats "search returned 0 hits" as a normal outcome.
            return UnifiedSearchResult(
                results=[],
                mode_queries={},
                total_after_rerank=0,
            )

        items: list[UnifiedSearchResultItem] = []
        for src in retrieve_result.sources:
            # Source VO does not currently surface raw payload fields like
            # source/source_id. Leaving them empty here is acceptable for the
            # initial release — consumers identify upstream records via
            # document_id, then call DELETE /by-source if cascade is needed.
            items.append(
                UnifiedSearchResultItem(
                    chunk_id=src.chunk_id,
                    score=src.score,
                    kb_id=src.kb_id,
                    content=src.content_snippet,
                    document_id=src.document_id,
                    document_name=src.document_name,
                    source="",
                    source_id="",
                )
            )

        logger.info(
            "rag.unified_search",
            tenant_id=command.tenant_id,
            kb_count=len(command.kb_ids),
            modes=command.retrieval_modes,
            filter_keys=list(command.filters.keys()) if command.filters else [],
            result_count=len(items),
        )

        return UnifiedSearchResult(
            results=items,
            mode_queries=retrieve_result.mode_queries,
            total_after_rerank=len(items),
        )
