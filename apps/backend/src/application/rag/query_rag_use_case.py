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
from src.infrastructure.observability.agent_trace_collector import AgentTraceCollector
from src.infrastructure.rag.llm_reranker import llm_rerank

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
    rerank_enabled: bool = False
    rerank_model: str = ""
    rerank_top_n: int = 20       # embedding 召回數量


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
        api_key_resolver=None,
        record_usage=None,  # Token-Gov.0: 給 reranker 記錄 token 用量
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._llm_service = llm_service
        self._api_key_resolver = api_key_resolver  # async (provider_name) -> str
        self._record_usage = record_usage

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

        search_limit = (
            command.rerank_top_n
            if command.rerank_enabled
            else command.top_k
        )
        t0 = time.perf_counter()
        search_tasks = [
            self._vector_store.search(
                collection=f"kb_{kid}",
                query_vector=query_vector,
                limit=search_limit,
                score_threshold=command.score_threshold,
                filters={"tenant_id": command.tenant_id},
            )
            for kid in effective_kb_ids
        ]
        search_results = await asyncio.gather(*search_tasks)
        # QualityEdit.1: 保留 kb_id 歸屬（跨 KB 搜尋時每筆 result 源頭 kb）
        all_results_with_kb: list[tuple[str, Any]] = [
            (kid, r)
            for kid, batch in zip(effective_kb_ids, search_results)
            for r in batch
        ]
        all_results_with_kb.sort(key=lambda pair: pair[1].score, reverse=True)
        all_results = [r for _, r in all_results_with_kb]
        _result_kb_map = {r.id: kid for kid, r in all_results_with_kb}
        search_ms = int((time.perf_counter() - t0) * 1000)

        # Trace: vector search results
        # parent_id 用 label-based 反查 — ContextVar tool_parent() 在 LLM parallel
        # tool calls 場景會被「最後一個 tool」覆蓋（例如同時 emit rag_query +
        # transfer_to_human_agent 時，tool_parent 會指向 transfer 而非 rag_query）。
        # 用 find_last_node_by 確保 parent 永遠指向真正的 rag_query 呼叫者。
        AgentTraceCollector.add_node(
            node_type="tool_result",
            label="RAG 向量搜尋",
            parent_id=(
                AgentTraceCollector.find_last_node_by("tool_call", "rag_query")
                or AgentTraceCollector.tool_parent()
            ),
            start_ms=AgentTraceCollector.offset_ms() - search_ms,
            end_ms=AgentTraceCollector.offset_ms(),
            result_count=len(all_results),
            top_score=round(all_results[0].score, 4) if all_results else 0,
            kb_ids=effective_kb_ids,
            chunk_scores=[
                {"rank": i + 1, "score": round(r.score, 4), "preview": r.payload.get("content", "")[:80]}
                for i, r in enumerate(all_results)
            ],
        )

        # Rerank if enabled
        final_k = command.top_k
        if command.rerank_enabled and len(all_results) > final_k:
            rerank_input = all_results[:search_limit]
            reranked = await llm_rerank(
                query=command.query,
                chunks=[
                    {"content": r.payload.get("content", ""), "_idx": i}
                    for i, r in enumerate(rerank_input)
                ],
                model=command.rerank_model or "claude-haiku-4-5-20251001",
                top_k=final_k,
                record_usage=self._record_usage,
                tenant_id=command.tenant_id,
            )
            results = []
            for rc in reranked:
                idx = rc.get("_idx", 0)
                if idx < len(rerank_input):
                    results.append(rerank_input[idx])
        else:
            results = all_results[:command.top_k]

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
                kb_id=_result_kb_map.get(r.id, ""),
            )
            for r in results
        ]

        return RetrieveResult(
            chunks=[r.payload["content"] for r in results],
            sources=sources,
        )

