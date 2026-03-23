"""RAG 查詢用例"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.services import EmbeddingService, LLMService, VectorStore
from src.domain.rag.value_objects import RAGResponse, Source
from src.domain.shared.exceptions import EntityNotFoundError, NoRelevantKnowledgeError
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

RAG_SYSTEM_PROMPT = (
    "你是一個專業的電商客服助手。根據提供的知識庫內容回答使用者的問題。"
    "請確保回答準確、有幫助，並引用知識庫中的相關資訊。"
    "如果知識庫中沒有相關資訊，請誠實告知。"
)


@dataclass(frozen=True)
class QueryRAGCommand:
    tenant_id: str
    kb_id: str
    query: str
    top_k: int = 5
    score_threshold: float = 0.3
    kb_ids: list[str] | None = None


@dataclass(frozen=True)
class RetrieveResult:
    """embed + search 結果（不含 LLM 生成），供 Agent tool 使用"""

    chunks: list[str]
    sources: list[Source]


class QueryRAGUseCase:
    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        llm_service: LLMService,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._llm_service = llm_service

    async def execute(self, command: QueryRAGCommand) -> RAGResponse:
        t_total = time.perf_counter()
        effective_kb_ids = command.kb_ids or [command.kb_id]

        # Validate all KBs exist
        for kid in effective_kb_ids:
            kb = await self._kb_repo.find_by_id(kid)
            if kb is None:
                raise EntityNotFoundError("KnowledgeBase", kid)

        t0 = time.perf_counter()
        query_vector = await self._embedding_service.embed_query(command.query)
        embed_ms = int((time.perf_counter() - t0) * 1000)

        # Search across all KBs in parallel and merge results
        t0 = time.perf_counter()
        search_tasks = [
            self._vector_store.search(
                collection=f"kb_{kid}",
                query_vector=query_vector,
                limit=command.top_k,
                score_threshold=command.score_threshold,
                filters={"tenant_id": command.tenant_id},
            )
            for kid in effective_kb_ids
        ]
        search_results = await asyncio.gather(*search_tasks)
        all_results = [r for batch in search_results for r in batch]
        search_ms = int((time.perf_counter() - t0) * 1000)

        # Sort by score descending, take top_k
        all_results.sort(key=lambda r: r.score, reverse=True)
        results = all_results[: command.top_k]

        if not results:
            logger.info(
                "rag.query.no_results",
                embed_ms=embed_ms,
                search_ms=search_ms,
                kb_count=len(effective_kb_ids),
            )
            raise NoRelevantKnowledgeError(command.query)

        context = "\n---\n".join(
            r.payload["content"] for r in results
        )

        t0 = time.perf_counter()
        llm_result = await self._llm_service.generate(
            RAG_SYSTEM_PROMPT, command.query, context
        )
        llm_ms = int((time.perf_counter() - t0) * 1000)
        total_ms = int((time.perf_counter() - t_total) * 1000)

        logger.info(
            "rag.query.done",
            total_ms=total_ms,
            embed_ms=embed_ms,
            search_ms=search_ms,
            llm_ms=llm_ms,
            kb_count=len(effective_kb_ids),
            result_count=len(results),
        )

        sources = [
            Source(
                document_name=r.payload.get("document_name", ""),
                content_snippet=r.payload["content"][:200],
                score=r.score,
                chunk_id=r.id,
                document_id=r.payload.get("document_id", ""),
            )
            for r in results
        ]

        return RAGResponse(
            answer=llm_result.text,
            sources=sources,
            query=command.query,
            tenant_id=command.tenant_id,
            knowledge_base_id=effective_kb_ids[0],
            usage=llm_result.usage,
        )

    async def retrieve(self, command: QueryRAGCommand) -> RetrieveResult:
        """只做 embed + search，不呼叫 LLM。供 Agent tool 使用。"""
        t_total = time.perf_counter()
        effective_kb_ids = command.kb_ids or [command.kb_id]

        for kid in effective_kb_ids:
            kb = await self._kb_repo.find_by_id(kid)
            if kb is None:
                raise EntityNotFoundError("KnowledgeBase", kid)

        t0 = time.perf_counter()
        query_vector = await self._embedding_service.embed_query(command.query)
        embed_ms = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        search_tasks = [
            self._vector_store.search(
                collection=f"kb_{kid}",
                query_vector=query_vector,
                limit=command.top_k,
                score_threshold=command.score_threshold,
                filters={"tenant_id": command.tenant_id},
            )
            for kid in effective_kb_ids
        ]
        search_results = await asyncio.gather(*search_tasks)
        all_results = [r for batch in search_results for r in batch]
        search_ms = int((time.perf_counter() - t0) * 1000)

        all_results.sort(key=lambda r: r.score, reverse=True)
        results = all_results[: command.top_k]

        if not results:
            logger.info(
                "rag.retrieve.no_results",
                embed_ms=embed_ms,
                search_ms=search_ms,
                kb_count=len(effective_kb_ids),
            )
            raise NoRelevantKnowledgeError(command.query)

        total_ms = int((time.perf_counter() - t_total) * 1000)
        logger.info(
            "rag.retrieve.done",
            total_ms=total_ms,
            embed_ms=embed_ms,
            search_ms=search_ms,
            kb_count=len(effective_kb_ids),
            result_count=len(results),
        )

        sources = [
            Source(
                document_name=r.payload.get("document_name", ""),
                content_snippet=r.payload["content"][:200],
                score=r.score,
                chunk_id=r.id,
                document_id=r.payload.get("document_id", ""),
            )
            for r in results
        ]

        return RetrieveResult(
            chunks=[r.payload["content"] for r in results],
            sources=sources,
        )

    async def execute_stream(
        self, command: QueryRAGCommand
    ) -> AsyncIterator[dict]:
        kb = await self._kb_repo.find_by_id(command.kb_id)
        if kb is None:
            raise EntityNotFoundError("KnowledgeBase", command.kb_id)

        query_vector = await self._embedding_service.embed_query(command.query)

        results = await self._vector_store.search(
            collection=f"kb_{command.kb_id}",
            query_vector=query_vector,
            limit=command.top_k,
            score_threshold=command.score_threshold,
            filters={"tenant_id": command.tenant_id},
        )

        if not results:
            raise NoRelevantKnowledgeError(command.query)

        context = "\n---\n".join(
            r.payload["content"] for r in results
        )

        usage_collector: dict = {}
        async for token in self._llm_service.generate_stream(
            RAG_SYSTEM_PROMPT, command.query, context,
            usage_collector=usage_collector,
        ):
            yield {"type": "token", "content": token}

        sources = [
            Source(
                document_name=r.payload.get("document_name", ""),
                content_snippet=r.payload["content"][:200],
                score=r.score,
                chunk_id=r.id,
                document_id=r.payload.get("document_id", ""),
            )
            for r in results
        ]
        yield {"type": "sources", "sources": [s.to_dict() for s in sources]}

        if usage_collector:
            yield {"type": "usage", **usage_collector}

        yield {"type": "done"}
