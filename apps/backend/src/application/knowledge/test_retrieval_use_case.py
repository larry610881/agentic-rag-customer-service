"""Test Retrieval Use Case (Playground) — S-KB-Studio.1.

Issue #43 Stage 2.6: 改為 thin wrapper of ``QueryRAGUseCase``。
Playground 跟真實對話走同一條程式路徑（multi-mode retrieve / rerank /
threshold / bot context）— Playground 顯示的就是 bot 真實會呼叫的結果。

額外功能（real RAG 不做）
-----------------------
1. 跨租戶 admin bypass — 透過 ``ensure_kb_accessible``
2. ``include_conv_summaries`` — 同時搜對話摘要 collection
3. 回傳每個 retrieval mode 改寫後的 query 字串（debug 用）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.application.rag.query_rag_use_case import (
    QueryRAGCommand,
    QueryRAGUseCase,
)
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.retrieval_mode import normalize_modes
from src.domain.rag.services import EmbeddingService, VectorStore
from src.domain.shared.exceptions import (
    EntityNotFoundError,  # noqa: F401  # 保留供 caller import 兼容
    NoRelevantKnowledgeError,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TestRetrievalCommand:
    kb_id: str
    tenant_id: str
    query: str
    top_k: int = 5
    include_conv_summaries: bool = False
    actor: str = ""
    # === Real-RAG 對齊參數 ===
    score_threshold: float = 0.0  # Playground 預設 0.0；real RAG 預設 0.3
    rerank_enabled: bool = False
    rerank_model: str = ""  # 空 → llm_rerank 預設 (claude-haiku-4-5)
    rerank_top_n: int = 20
    # Issue #43 — multi-mode retrieval
    # retrieval_modes 為空 → 兼容舊參數 query_rewrite_enabled 自動轉換
    retrieval_modes: list[str] = field(default_factory=list)
    query_rewrite_enabled: bool = False  # Legacy toggle; 留作兼容
    query_rewrite_model: str = ""
    query_rewrite_extra_hint: str = ""
    hyde_enabled: bool = False  # Legacy 命名（modes 含 "hyde" = enabled）
    hyde_model: str = ""
    hyde_extra_hint: str = ""
    # 若指定 bot_id，rewrite/hyde 時會帶 bot.bot_prompt 作 context
    # → 模擬真實對話「同問題在不同 bot 下會被改寫成不同字串」
    bot_id: str = ""


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
    rewritten_query: str = ""  # Legacy: rewrite mode 改寫後字串
    # Issue #43 — 每個 retrieval mode 實際送 embed 的 query 字串
    mode_queries: dict[str, str] = field(default_factory=dict)


def _resolve_modes(command: TestRetrievalCommand) -> list[str]:
    """根據 command 解析最終 retrieval modes。

    優先用 ``retrieval_modes``；若空則從 legacy toggle 反推。
    至少回 ``["raw"]``，永遠不會空。
    """
    if command.retrieval_modes:
        return normalize_modes(list(command.retrieval_modes))
    modes: list[str] = ["raw"]
    if command.query_rewrite_enabled:
        modes.append("rewrite")
    if command.hyde_enabled:
        modes.append("hyde")
    return normalize_modes(modes)


class TestRetrievalUseCase:
    def __init__(
        self,
        kb_repo: KnowledgeBaseRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        chunk_context_service=None,  # 拿 api_key_resolver 給 LLM 用
        record_usage_use_case=None,  # rerank 記 token 用量
        bot_repository=None,  # 拿 bot.bot_prompt 給 rewrite/hyde 作 context
        query_rag_use_case: QueryRAGUseCase | None = None,
    ) -> None:
        self._kb_repo = kb_repo
        self._embed = embedding_service
        self._vs = vector_store
        self._context_service = chunk_context_service
        self._record_usage = record_usage_use_case
        self._bot_repo = bot_repository
        self._query_rag = query_rag_use_case

    def _api_key_resolver(self):
        cs = self._context_service
        if cs and hasattr(cs, "_api_key_resolver"):
            return cs._api_key_resolver
        return None

    async def execute(
        self, command: TestRetrievalCommand
    ) -> TestRetrievalResult:
        # 1. KB 存取檢查（含 system_admin bypass）
        # admin 訪問跨租戶 KB 時 effective_tenant_id = kb.tenant_id (真實 owner)
        # → Milvus filter 用此值，admin 才看得到該租戶的真實 chunks
        await ensure_kb_accessible(
            self._kb_repo, command.kb_id, command.tenant_id
        )
        if not command.query.strip():
            raise ValueError("query must not be empty")

        # 2. 載入 bot system prompt（rewrite/hyde 需要）
        bot_system_prompt = ""
        if command.bot_id and self._bot_repo:
            try:
                bot = await self._bot_repo.find_by_id(command.bot_id)
                if bot:
                    bot_system_prompt = bot.bot_prompt or ""
            except Exception:
                logger.warning(
                    "playground.bot_load_failed",
                    bot_id=command.bot_id,
                    exc_info=True,
                )

        # 3. 走 query_rag_use_case — 跟真實對話 100% 同程式路徑
        modes = _resolve_modes(command)
        # use ensure_kb_accessible 回傳 effective_tenant_id（admin 跨租戶用）
        _, effective_tenant_id = await ensure_kb_accessible(
            self._kb_repo, command.kb_id, command.tenant_id
        )
        rag_command = QueryRAGCommand(
            tenant_id=effective_tenant_id,
            kb_id=command.kb_id,
            query=command.query,
            top_k=command.top_k,
            score_threshold=command.score_threshold,
            rerank_enabled=command.rerank_enabled,
            rerank_model=command.rerank_model,
            rerank_top_n=command.rerank_top_n,
            retrieval_modes=modes,
            query_rewrite_model=command.query_rewrite_model,
            query_rewrite_extra_hint=command.query_rewrite_extra_hint,
            hyde_model=command.hyde_model,
            hyde_extra_hint=command.hyde_extra_hint,
            bot_system_prompt=bot_system_prompt,
        )

        chunk_hits: list[RetrievalHit] = []
        mode_queries: dict[str, str] = {}
        try:
            assert self._query_rag is not None, (
                "QueryRAGUseCase must be injected"
            )
            rag_result = await self._query_rag.retrieve(rag_command)
            for src, content in zip(
                rag_result.sources, rag_result.chunks, strict=True
            ):
                chunk_hits.append(
                    RetrievalHit(
                        chunk_id=src.chunk_id,
                        content=content,
                        score=src.score,
                        source="chunk",
                        metadata={
                            "document_name": src.document_name,
                            "document_id": src.document_id,
                            "kb_id": src.kb_id,
                        },
                    )
                )
            mode_queries = dict(rag_result.mode_queries)
        except NoRelevantKnowledgeError:
            mode_queries = {}

        # 4. 取一條 query vector 用來搜 conv_summaries（若需要）
        # 也用來 fill query_vector_dim metadata
        ref_query = mode_queries.get("rewrite") or mode_queries.get(
            "raw"
        ) or command.query
        query_vector = await self._embed.embed_query(ref_query)

        if command.include_conv_summaries:
            search_limit = (
                command.rerank_top_n
                if command.rerank_enabled
                else command.top_k
            )
            try:
                conv_results = await self._vs.search(
                    collection="conv_summaries",
                    query_vector=query_vector,
                    limit=search_limit,
                    score_threshold=command.score_threshold,
                    filters={"tenant_id": effective_tenant_id},
                )
                chunk_hits.extend(
                    RetrievalHit(
                        chunk_id=r.id,
                        content=(r.payload or {}).get("summary", ""),
                        score=r.score,
                        source="conv_summary",
                        metadata=r.payload or {},
                    )
                    for r in conv_results
                )
            except Exception:
                logger.warning("playground.conv_summary_search_failed", exc_info=True)

        chunk_hits.sort(key=lambda h: h.score, reverse=True)

        # Legacy 欄位：rewrite mode 改寫後字串（若有）
        rewritten_query = mode_queries.get("rewrite", "")
        filter_expr = f'tenant_id == "{effective_tenant_id}"'

        return TestRetrievalResult(
            results=chunk_hits,
            filter_expr=filter_expr,
            query_vector_dim=len(query_vector),
            rewritten_query=rewritten_query,
            mode_queries=mode_queries,
        )
