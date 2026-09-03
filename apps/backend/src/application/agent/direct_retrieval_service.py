"""workflow 快速道（direct_retrieval）共用實作（Issue #61；channel-parity 債務 #1）

原本只存在於 LINE 轉接器（`handle_webhook_use_case._try_direct_retrieval`），web /
widget 永遠付 ReAct 決策輪。抽成 application 層共用服務後，三通路以同一份邏輯：
「以意圖分類產出的改寫查詢直接檢索 → 門檻判定 → 組出單次生成 prompt」。
生成本身仍由各通路呼叫 agent_service（web 要串流），服務只回傳「怎麼生成」的 plan。

快速道 profile（Issue #61 / #66）：rewrite / HyDE 一律關（raw-only）；rerank 由呼叫端依
bot.mode 決定——fast 一律關（零額外 LLM），deep 的 worker 快速道依 bot / worker 設定。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

logger = structlog.get_logger(__name__)

_CONTEXT_MAX_CHARS = 8000
_DM_CONTEXT_MAX_CHARS = 4000


@dataclass
class DirectRetrievalPlan:
    """快速道生成計畫：各通路以此呼叫 agent_service。"""

    system_prompt: str
    enabled_tools: list[str]
    sources: list[Any] = field(default_factory=list)  # Source | dict（DM）
    max_tool_calls: int = 1
    top_score: float = 0.0
    chunk_count: int = 0


class DirectRetrievalService:
    def __init__(
        self,
        query_rag_use_case: Any,
        dm_image_query_tool: Any | None = None,
        allow_rerank: bool = True,
    ) -> None:
        self._query_rag = query_rag_use_case
        self._dm_tool = dm_image_query_tool
        # 預設值；呼叫端可依 bot.mode 逐次覆寫（Issue #66）
        self._allow_rerank = allow_rerank

    async def plan(
        self,
        *,
        tenant_id: str,
        bot: Any,
        kb_id: str,
        kb_ids: list[str],
        system_prompt: str | None,
        enabled_tools: list[str] | None,
        tool_rag_params: dict | None,
        user_message: str,
        retrieval_query: str = "",
        allow_rerank: bool | None = None,
    ) -> DirectRetrievalPlan | None:
        """直接檢索 → 門檻判定 → 生成 plan。回 None 代表升級完整 ReAct。"""
        if self._query_rag is None or not kb_ids:
            return None
        from src.application.rag.query_rag_use_case import QueryRAGCommand

        threshold = bot.llm_params.rag_score_threshold
        search_query = (retrieval_query or "").strip() or user_message
        t_dr = AgentTraceCollector.offset_ms()

        # DM 圖卡：與文字檢索並行呼叫 DM 工具本體（image_url 不在向量 payload）
        dm_task = None
        dm_tool = self._dm_tool
        if dm_tool is not None and "query_dm_with_image" in (enabled_tools or []):
            dm_params = (tool_rag_params or {}).get("query_dm_with_image", {}) or {}
            dm_kb_ids = dm_params.get("kb_ids") or kb_ids
            dm_task = asyncio.create_task(dm_tool.invoke(
                tenant_id=tenant_id,
                kb_id=dm_kb_ids[0] if dm_kb_ids else kb_id,
                query=search_query,
                kb_ids=dm_kb_ids,
                top_k=dm_params.get("rag_top_k") or bot.llm_params.rag_top_k,
                score_threshold=dm_params.get("rag_score_threshold") or threshold,
            ))

        # M16：讀 worker 為 rag_query 設的 per-tool 參數，缺時退回 bot 全域
        rq = (tool_rag_params or {}).get("rag_query", {}) or {}
        rq_kb_ids = rq.get("kb_ids") or kb_ids
        score_threshold = float(
            rq["rag_score_threshold"]
            if rq.get("rag_score_threshold") is not None
            else threshold
        )
        rerank_enabled = (
            rq.get("rerank_enabled")
            if rq.get("rerank_enabled") is not None
            else bot.rerank_enabled
        )
        effective_allow = self._allow_rerank if allow_rerank is None else allow_rerank
        if not effective_allow:
            rerank_enabled = False  # fast profile：零額外 LLM
        try:
            rr = await self._query_rag.retrieve(QueryRAGCommand(
                tenant_id=tenant_id,
                kb_id=(rq_kb_ids[0] if rq_kb_ids else kb_id),
                query=search_query,
                top_k=rq.get("rag_top_k") or bot.llm_params.rag_top_k,
                score_threshold=score_threshold,
                kb_ids=rq_kb_ids,
                rerank_enabled=bool(rerank_enabled),
                rerank_model=rq.get("rerank_model") or bot.rerank_model,
                rerank_top_n=rq.get("rerank_top_n") or bot.rerank_top_n,
                retrieval_modes=["raw"],  # 快速道不做 rewrite / HyDE
            ))
        except Exception:
            logger.warning("direct_retrieval.error", exc_info=True)
            if dm_task is not None:
                dm_task.cancel()
            AgentTraceCollector.add_node(
                node_type="escalated",
                label="快速道檢索異常 → 升級 ReAct",
                parent_id=None,
                start_ms=t_dr,
                end_ms=AgentTraceCollector.offset_ms(),
                reason="retrieval_error",
            )
            return None

        dm_context = ""
        dm_sources: list[dict] = []
        if dm_task is not None:
            try:
                dm_res = await dm_task
                if dm_res and dm_res.get("success"):
                    dm_context = dm_res.get("context") or ""
                    dm_sources = dm_res.get("sources") or []
            except Exception:
                logger.warning("direct_retrieval.dm_error", exc_info=True)

        dm_top = max((float(d.get("score") or 0.0) for d in dm_sources), default=0.0)
        top_score = max(max((s.score for s in rr.sources), default=0.0), dm_top)
        AgentTraceCollector.add_node(
            node_type="direct_retrieval",
            label=f"快速道檢索（{len(rr.sources)} 筆，top {top_score:.2f}）",
            parent_id=None,
            start_ms=t_dr,
            end_ms=AgentTraceCollector.offset_ms(),
            chunk_count=len(rr.sources),
            top_score=round(top_score, 4),
            search_query=search_query,
            query_rewritten=search_query != user_message,
        )
        if not rr.sources or top_score < threshold:
            AgentTraceCollector.add_node(
                node_type="escalated",
                label="檢索未過門檻 → 升級 ReAct",
                parent_id=None,
                start_ms=AgentTraceCollector.offset_ms(),
                end_ms=AgentTraceCollector.offset_ms(),
                reason="low_score",
                top_score=round(top_score, 4),
            )
            return None

        context_block = "\n\n---\n\n".join(
            c for c in rr.chunks if c
        )[:_CONTEXT_MAX_CHARS]
        if dm_context:
            context_block += (
                "\n\n【DM 型錄相關內容】\n" + dm_context[:_DM_CONTEXT_MAX_CHARS]
            )
        # 轉真人工具保留：worker prompt 教模型查不到就轉真人，拔光工具會讓模型
        # 把工具名稱當文字裸吐（Larry 實測「多少門市」案例）
        fast_tools = (
            ["transfer_to_human_agent"]
            if "transfer_to_human_agent" in (enabled_tools or [])
            else []
        )
        fast_prompt = (
            (system_prompt or "")
            + "\n\n【知識庫檢索結果（依相關度排序）】\n"
            + context_block
            + "\n【檢索結果結束】\n"
            + "請依上述檢索結果回答使用者問題；"
            + "結果未涵蓋時誠實告知並引導聯絡客服，禁止編造。"
            + (
                "檢索工具已由系統代為執行完畢，"
                "除 transfer_to_human_agent（轉真人）外無其他可用工具；"
                if fast_tools
                else "本回覆模式下無任何可用工具；"
            )
            + "嚴禁在回覆文字中輸出任何工具名稱。"
        )
        return DirectRetrievalPlan(
            system_prompt=fast_prompt,
            enabled_tools=fast_tools,
            sources=list(rr.sources) + list(dm_sources),
            top_score=top_score,
            chunk_count=len(rr.sources),
        )
