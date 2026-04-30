"""Test Retrieval Use Case (Playground) — S-KB-Studio.1.

驗 tenant chain → 可選 LLM query rewrite → VectorStore.search 帶 tenant filter
→ 可選 LLM rerank → 回傳 results + filter_expr + 改寫後 query。

跟 real RAG 對齊：score_threshold / rerank / query_rewrite 三個開關
（real bot 的 query rewrite 是 LLM ReAct 決策出工具呼叫時改寫，
 此處用獨立 LLM call 模擬，方便 admin 在 Playground 比對效果）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.services import EmbeddingService, VectorStore
from src.domain.shared.exceptions import (
    EntityNotFoundError,  # noqa: F401  # 保留供 caller import 兼容
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
    score_threshold: float = 0.0  # Playground 預設 0.0 看完整 top-K，real RAG 預設 0.3
    rerank_enabled: bool = False
    rerank_model: str = ""  # 空字串走 llm_rerank 預設 (claude-haiku-4-5)
    rerank_top_n: int = 20
    query_rewrite_enabled: bool = False
    query_rewrite_model: str = ""  # 空字串走預設 (claude-haiku-4-5)
    # 若指定 bot_id，rewrite 時會帶 bot.system_prompt 作 context
    # → 模擬真實對話「同一個問題在不同 bot 下會被改寫成不同字串」
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
    rewritten_query: str = ""  # 若 query_rewrite_enabled，記錄改寫後內容


# 通用 rewrite（沒指定 bot 時用）— 跟真實 bot 沒對齊，純 RAG 改寫示範
_GENERIC_REWRITE_PROMPT = (
    "你是 RAG 檢索查詢改寫助手。把使用者的問題改寫成適合向量檢索的查詢字串。\n"
    "\n"
    "規則：\n"
    "- 保留所有關鍵詞和專有名詞\n"
    "- 移除語氣詞（請、麻煩、想知道、可以告訴我等）\n"
    "- 必要時擴展常見同義詞\n"
    "- 保持中文，不要翻譯\n"
    "- 直接輸出改寫後字串，不要解釋、不要引號\n"
    "\n"
    "使用者問題：{query}\n"
    "\n"
    "改寫後："
)

# Bot-aware rewrite — 用 bot 自己的 system_prompt 作主，最小化 rewrite 指令
# 跟真實對話對齊：bot LLM 思考「我要呼叫 rag_query 用什麼 query」的決策過程
_BOT_REWRITE_INSTRUCTION = (
    "使用者問你：「{query}」\n"
    "\n"
    "假設你決定要呼叫 RAG 知識庫檢索工具來找答案，"
    "你會用什麼查詢字串去搜尋？以你的身分與領域知識決定查詢用詞。\n"
    "\n"
    "只輸出查詢字串本身，不要解釋、不要引號、不要前綴。"
)


async def _rewrite_query(
    raw_query: str,
    model: str,
    bot_system_prompt: str = "",
    api_key_resolver=None,
) -> str:
    """Use LLM to rewrite query for better vector retrieval.

    - 有 bot_system_prompt：用 bot 自己的 system prompt 作 SYSTEM block，
      最小化 rewrite 指令 → 真實對齊「bot 在那個角色下會怎麼搜尋」
    - 沒 bot：用通用 rewrite prompt，純 RAG 改寫
    """
    from src.domain.llm.prompt_block import BlockRole, PromptBlock
    from src.infrastructure.llm.llm_caller import call_llm

    spec = model or "anthropic:claude-haiku-4-5"
    try:
        if bot_system_prompt:
            # Bot-aware：bot prompt 作 system，user message 是極簡 rewrite 指令
            blocks = [
                PromptBlock(
                    text=bot_system_prompt,
                    role=BlockRole.SYSTEM,
                ),
                PromptBlock(
                    text=_BOT_REWRITE_INSTRUCTION.format(query=raw_query),
                    role=BlockRole.USER,
                ),
            ]
            result = await call_llm(
                model_spec=spec,
                prompt=blocks,
                max_tokens=200,
                api_key_resolver=api_key_resolver,
            )
        else:
            # 通用 rewrite — 沒 bot context 時的 baseline
            prompt = _GENERIC_REWRITE_PROMPT.format(query=raw_query)
            result = await call_llm(
                model_spec=spec,
                prompt=prompt,
                max_tokens=200,
                api_key_resolver=api_key_resolver,
            )
        rewritten = result.text.strip().strip('"').strip("「").strip("」")
        return rewritten or raw_query  # 改寫空字串 → fallback 原 query
    except Exception:
        logger.warning("playground.rewrite_failed", exc_info=True)
        return raw_query  # rewrite 失敗 → 沿用原 query 不擋 search


class TestRetrievalUseCase:
    def __init__(
        self,
        kb_repo: KnowledgeBaseRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        chunk_context_service=None,  # 拿 api_key_resolver 給 rewrite + rerank LLM 用
        record_usage_use_case=None,  # rerank 記 token 用量
        bot_repository=None,  # 拿 bot.system_prompt 給 rewrite 作 context
    ) -> None:
        self._kb_repo = kb_repo
        self._embed = embedding_service
        self._vs = vector_store
        self._context_service = chunk_context_service
        self._record_usage = record_usage_use_case
        self._bot_repo = bot_repository

    async def execute(
        self, command: TestRetrievalCommand
    ) -> TestRetrievalResult:
        # 統一 KB 存取檢查（含 system_admin bypass）
        # 重要：admin 訪問跨租戶 KB 時，effective_tenant_id = kb.tenant_id (真實 owner)
        # → Milvus filter 用此值，admin 才看得到該租戶的真實 chunks
        kb, effective_tenant_id = await ensure_kb_accessible(
            self._kb_repo, command.kb_id, command.tenant_id
        )
        if not command.query.strip():
            raise ValueError("query must not be empty")

        # 1. Optional query rewrite
        api_key_resolver = (
            self._context_service._api_key_resolver
            if self._context_service
            and hasattr(self._context_service, "_api_key_resolver")
            else None
        )
        if command.query_rewrite_enabled:
            # 若指定 bot_id 且 bot_repo 存在 → 拿 bot.system_prompt 作改寫 context
            bot_system_prompt = ""
            if command.bot_id and self._bot_repo:
                try:
                    bot = await self._bot_repo.find_by_id(command.bot_id)
                    if bot:
                        bot_system_prompt = bot.system_prompt or ""
                except Exception:
                    logger.warning(
                        "playground.bot_load_failed",
                        bot_id=command.bot_id,
                        exc_info=True,
                    )
            search_query = await _rewrite_query(
                command.query,
                command.query_rewrite_model,
                bot_system_prompt=bot_system_prompt,
                api_key_resolver=api_key_resolver,
            )
            rewritten_query = search_query
        else:
            search_query = command.query
            rewritten_query = ""

        # 2. Embed (rewrite 後或原 query)
        query_vector = await self._embed.embed_query(search_query)
        filters = {"tenant_id": effective_tenant_id}
        filter_expr = f'tenant_id == "{effective_tenant_id}"'

        # 3. Vector search — rerank 開時要先撈更多 candidates
        search_limit = (
            command.rerank_top_n
            if command.rerank_enabled
            else command.top_k
        )

        # 用 command.kb_id (str) 而非 kb.id (KnowledgeBaseId VO)
        # f-string with VO 會得到 "kb_KnowledgeBaseId(value='...')" 不是 "kb_<uuid>"
        # → Milvus collection 名稱含括號炸掉「查詢錯誤」
        collection = f"kb_{command.kb_id}"
        chunk_results = await self._vs.search(
            collection=collection,
            query_vector=query_vector,
            limit=search_limit,
            score_threshold=command.score_threshold,
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
                limit=search_limit,
                score_threshold=command.score_threshold,
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

        # 4. Optional LLM rerank (用 search_query — 跟向量搜尋一致)
        if command.rerank_enabled and len(hits) > command.top_k:
            from src.infrastructure.rag.llm_reranker import llm_rerank

            try:
                reranked = await llm_rerank(
                    query=search_query,
                    chunks=[
                        {"id": h.chunk_id, "content": h.content}
                        for h in hits
                    ],
                    model=command.rerank_model
                    or "claude-haiku-4-5-20251001",
                    top_k=command.top_k,
                    record_usage=self._record_usage,
                    tenant_id=effective_tenant_id,
                )
                # rerank 後重排 + 取前 top_k
                hits_by_id = {h.chunk_id: h for h in hits}
                hits = [
                    hits_by_id[rc["id"]]
                    for rc in reranked
                    if rc["id"] in hits_by_id
                ]
            except Exception:
                logger.warning("playground.rerank_failed", exc_info=True)
                # rerank 失敗 → 沿用原排序，截 top_k
                hits.sort(key=lambda h: h.score, reverse=True)
                hits = hits[: command.top_k]
        else:
            hits.sort(key=lambda h: h.score, reverse=True)
            hits = hits[: command.top_k]

        return TestRetrievalResult(
            results=hits,
            filter_expr=filter_expr,
            query_vector_dim=len(query_vector),
            rewritten_query=rewritten_query,
        )
