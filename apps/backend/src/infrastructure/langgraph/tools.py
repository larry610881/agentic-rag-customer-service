"""LangGraph Tool wrappers — 包裝 domain 工具服務為 LangGraph tools"""

from typing import Any

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.domain.shared.exceptions import NoRelevantKnowledgeError


class RAGQueryTool:
    """RAG 知識查詢工具"""

    name = "rag_query"
    description = "查詢知識庫回答用戶問題，適用於退貨政策、使用說明等知識型問題"

    def __init__(
        self,
        query_rag_use_case: QueryRAGUseCase,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> None:
        self._use_case = query_rag_use_case
        self._top_k = top_k
        self._score_threshold = score_threshold

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
        try:
            result = await self._use_case.execute(
                QueryRAGCommand(
                    tenant_id=tenant_id,
                    kb_id=kb_id,
                    query=query,
                    kb_ids=kb_ids,
                    top_k=top_k if top_k is not None else self._top_k,
                    score_threshold=score_threshold if score_threshold is not None else self._score_threshold,
                )
            )
            return {
                "success": True,
                "answer": result.answer,
                "sources": [s.to_dict() for s in result.sources],
            }
        except NoRelevantKnowledgeError:
            return {
                "success": True,
                "answer": "知識庫中沒有找到相關資訊。",
                "sources": [],
            }
