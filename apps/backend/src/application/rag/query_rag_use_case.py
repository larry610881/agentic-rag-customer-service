"""RAG 查詢用例"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from src.application.rag._hyde_generator import generate_hyde
from src.application.rag._query_rewriter import rewrite_query
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.retrieval_mode import (
    RetrievalMode,
    normalize_modes,
    validate_modes,
)
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
    # Issue #43 — Bot-level RAG retrieval modes
    # 至少 1 個（執行時 validate）；多選會走 multi-query retrieval
    retrieval_modes: list[str] = field(default_factory=lambda: ["raw"])
    query_rewrite_model: str = ""
    query_rewrite_extra_hint: str = ""
    hyde_model: str = ""
    hyde_extra_hint: str = ""
    bot_system_prompt: str = ""  # rewrite/hyde 用 bot 視角
    # Issue #44 Phase 3 — Unified Search: caller-supplied metadata filter
    # merged into Milvus filter expression alongside tenant_id. Use first-class
    # field names (source, source_id, document_id, content_type, language).
    # Producer-specific keys (e.g. actor_role) live in `extra` JSON and are
    # not yet supported here — Phase 4 work.
    extra_filters: dict[str, Any] | None = None


@dataclass(frozen=True)
class RetrieveResult:
    """embed + search 結果（不含 LLM 生成），供 Agent tool 使用"""

    chunks: list[str]
    sources: list[Source]
    # Issue #43 — multi-mode 觀測欄位（Playground / debug 用）
    mode_queries: dict[str, str] = field(default_factory=dict)


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

    async def _resolve_mode_queries(
        self, command: QueryRAGCommand, modes: list[str]
    ) -> dict[str, str]:
        """為每個 mode 解析出實際送 embed 的 query 字串。

        - raw: 原始 query
        - rewrite: LLM 改寫
        - hyde: LLM 生成假答案
        rewrite/hyde 失敗會 fallback raw query（不擋下游 search）。
        """
        # gen_tasks: list of (mode, awaitable returning generated query string)
        gen_tasks: list[tuple[str, Any]] = []
        if RetrievalMode.REWRITE.value in modes:
            gen_tasks.append((
                RetrievalMode.REWRITE.value,
                rewrite_query(
                    command.query,
                    model=command.query_rewrite_model,
                    bot_system_prompt=command.bot_system_prompt,
                    extra_hint=command.query_rewrite_extra_hint,
                    api_key_resolver=self._api_key_resolver,
                ),
            ))
        if RetrievalMode.HYDE.value in modes:
            gen_tasks.append((
                RetrievalMode.HYDE.value,
                generate_hyde(
                    command.query,
                    model=command.hyde_model,
                    bot_system_prompt=command.bot_system_prompt,
                    extra_hint=command.hyde_extra_hint,
                    api_key_resolver=self._api_key_resolver,
                ),
            ))

        mode_queries: dict[str, str] = {}
        if RetrievalMode.RAW.value in modes:
            mode_queries[RetrievalMode.RAW.value] = command.query
        if gen_tasks:
            results = await asyncio.gather(
                *(t for _, t in gen_tasks), return_exceptions=False
            )
            for (mode, _), text in zip(gen_tasks, results, strict=True):
                mode_queries[mode] = text or command.query
        return mode_queries

    async def retrieve(self, command: QueryRAGCommand) -> RetrieveResult:
        """只做 embed + search，不呼叫 LLM。供 Agent tool 使用。

        Issue #43: 多 retrieval mode（raw / rewrite / hyde）並行展開 →
        對每個 (mode, kb_id) 呼叫向量搜尋 → 結果 union by chunk_id
        （保留最高分）→ 既有 rerank + top_k 流程不變。
        """
        t_total = time.perf_counter()
        effective_kb_ids = command.kb_ids or [command.kb_id]

        # Issue #43 — modes 驗證 + normalize
        # 空 list = explicit error；不會 silent fallback（caller 該明確傳 ["raw"]）
        if not command.retrieval_modes:
            raise ValueError(
                "retrieval_modes must contain at least 1 mode"
            )
        modes = normalize_modes(list(command.retrieval_modes))
        validate_modes(modes)

        for kid in effective_kb_ids:
            kb = await self._kb_repo.find_by_id(kid)
            if kb is None:
                raise EntityNotFoundError("KnowledgeBase", kid)

        # 1. 為每個 mode 產出實際 query 字串（rewrite/hyde 並行 LLM call）
        t0 = time.perf_counter()
        mode_queries = await self._resolve_mode_queries(command, modes)
        gen_ms = int((time.perf_counter() - t0) * 1000)

        # 2. 為每條 query 並行 embed
        t0 = time.perf_counter()
        ordered_modes = [m for m in modes if m in mode_queries]
        query_vectors_list = await asyncio.gather(
            *(
                self._embedding_service.embed_query(mode_queries[m])
                for m in ordered_modes
            )
        )
        mode_vectors: dict[str, list[float]] = dict(
            zip(ordered_modes, query_vectors_list, strict=True)
        )
        embed_ms = int((time.perf_counter() - t0) * 1000)

        search_limit = (
            command.rerank_top_n
            if command.rerank_enabled
            else command.top_k
        )

        # 3. 對 (mode × kb_id) 笛卡爾積並行搜尋
        t0 = time.perf_counter()
        plan: list[tuple[str, str]] = [
            (mode, kid)
            for mode in ordered_modes
            for kid in effective_kb_ids
        ]
        # Issue #44 Phase 3: tenant_id is mandatory; caller may supply
        # additional first-class metadata filters via extra_filters. We
        # explicitly drop any incoming tenant_id key so a misbehaving
        # caller cannot widen the tenant scope.
        base_filters: dict[str, Any] = {"tenant_id": command.tenant_id}
        if command.extra_filters:
            for k, v in command.extra_filters.items():
                if k == "tenant_id":
                    continue
                base_filters[k] = v

        search_tasks = [
            self._vector_store.search(
                collection=f"kb_{kid}",
                query_vector=mode_vectors[mode],
                limit=search_limit,
                score_threshold=command.score_threshold,
                filters=base_filters,
            )
            for mode, kid in plan
        ]
        search_results = await asyncio.gather(*search_tasks)

        # 4. Union by chunk_id — 保留最高分；記錄該 chunk 由哪些 mode 命中
        # mode_hit_map: chunk_id → set(modes); kb_map: chunk_id → kb_id
        merged: dict[str, Any] = {}
        kb_map: dict[str, str] = {}
        mode_hit_map: dict[str, set[str]] = {}
        for (mode, kid), batch in zip(plan, search_results, strict=True):
            for r in batch:
                cid = r.id
                mode_hit_map.setdefault(cid, set()).add(mode)
                if cid not in merged or r.score > merged[cid].score:
                    merged[cid] = r
                    kb_map[cid] = kid
        all_results: list[Any] = sorted(
            merged.values(), key=lambda r: r.score, reverse=True
        )
        search_ms = int((time.perf_counter() - t0) * 1000)

        # Trace: vector search results
        # parent_id 用 label-based 反查 — ContextVar tool_parent() 在 LLM parallel
        # tool calls 場景會被「最後一個 tool」覆蓋。
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
            modes=ordered_modes,
            mode_queries={m: mode_queries[m] for m in ordered_modes},
            chunk_scores=[
                {
                    "rank": i + 1,
                    "score": round(r.score, 4),
                    "preview": r.payload.get("content", "")[:80],
                    "modes": sorted(mode_hit_map.get(r.id, set())),
                }
                for i, r in enumerate(all_results)
            ],
        )

        # 5. Rerank if enabled — 用 raw query 作 rerank judge
        # （rerank LLM 看的是「使用者真正想問什麼」，不是改寫過或假答案）
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
                gen_ms=gen_ms,
                modes=ordered_modes,
                kb_count=len(effective_kb_ids),
            )
            raise NoRelevantKnowledgeError(command.query)

        total_ms = int((time.perf_counter() - t_total) * 1000)
        logger.info(
            "rag.retrieve.done",
            total_ms=total_ms,
            embed_ms=embed_ms,
            search_ms=search_ms,
            gen_ms=gen_ms,
            modes=ordered_modes,
            kb_count=len(effective_kb_ids),
            result_count=len(results),
        )

        sources = [
            Source(
                document_name=r.payload.get("document_name", ""),
                content_snippet=(r.payload.get("content") or "")[:200],
                score=r.score,
                chunk_id=r.id,
                document_id=r.payload.get("document_id", ""),
                kb_id=kb_map.get(r.id, ""),
            )
            for r in results
        ]

        return RetrieveResult(
            chunks=[r.payload.get("content", "") for r in results],
            sources=sources,
            mode_queries=mode_queries,
        )

