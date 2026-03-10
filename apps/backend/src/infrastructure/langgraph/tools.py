"""LangGraph Tool wrappers — 包裝 domain 工具服務為 LangGraph tools"""

import time
from typing import Any

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.domain.shared.exceptions import NoRelevantKnowledgeError
from src.infrastructure.observability.rag_tracer import RAGTracer


class RAGQueryTool:
    """RAG 知識查詢工具"""

    name = "rag_query"
    description = (
        "查詢知識庫回答用戶問題。適用於：商品推薦、分類導覽、退貨政策、"
        "使用說明、品牌介紹等需要綜合判斷的問題。"
        "當用戶問「推薦」「適合」「有什麼」「哪些」類問題時優先使用此工具。"
    )

    def __init__(
        self,
        query_rag_use_case: QueryRAGUseCase,
        top_k: int = 5,
        score_threshold: float = 0.3,
        tracer: RAGTracer | None = None,
    ) -> None:
        self._use_case = query_rag_use_case
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._tracer = tracer

    async def invoke(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        *,
        kb_ids: list[str] | None = None,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        trace = None

        if self._tracer:
            trace = self._tracer.start_trace(query, tenant_id)

        try:
            result = await self._use_case.retrieve(
                QueryRAGCommand(
                    tenant_id=tenant_id,
                    kb_id=kb_id,
                    query=query,
                    kb_ids=kb_ids,
                    top_k=top_k if top_k is not None else self._top_k,
                    score_threshold=(
                        score_threshold
                        if score_threshold is not None
                        else self._score_threshold
                    ),
                )
            )

            elapsed_ms = (time.perf_counter() - t0) * 1000
            if trace:
                trace.add_step(
                    "retrieve", elapsed_ms, chunk_count=len(result.chunks)
                )
                trace.chunk_count = len(result.chunks)
                trace.finish(elapsed_ms)

            return {
                "success": True,
                "context": "\n---\n".join(result.chunks),
                "sources": [s.to_dict() for s in result.sources],
            }
        except NoRelevantKnowledgeError:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if trace:
                trace.add_step("retrieve", elapsed_ms, chunk_count=0)
                trace.finish(elapsed_ms)
            return {
                "success": True,
                "context": "",
                "sources": [],
            }
