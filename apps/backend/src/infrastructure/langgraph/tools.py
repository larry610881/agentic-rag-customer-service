"""LangGraph Tool wrappers — 包裝 domain 工具服務為 LangGraph tools"""

from typing import Any

from src.application.agent.order_lookup_use_case import OrderLookupUseCase
from src.application.agent.product_search_use_case import ProductSearchUseCase
from src.application.agent.ticket_creation_use_case import TicketCreationUseCase
from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.domain.knowledge.repository import KnowledgeBaseRepository
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


class OrderLookupTool:
    """訂單查詢工具"""

    name = "order_lookup"
    description = "查詢訂單狀態、配送進度，適用於用戶查詢特定訂單"

    def __init__(self, use_case: OrderLookupUseCase) -> None:
        self._use_case = use_case

    async def invoke(self, order_id: str) -> dict[str, Any]:
        result = await self._use_case.execute(order_id)
        return {
            "success": result.success,
            "data": result.data,
            "error_message": result.error_message,
        }


class ProductSearchTool:
    """商品搜尋工具"""

    name = "product_search"
    description = "搜尋商品資訊，適用於用戶查詢產品或推薦"

    def __init__(self, use_case: ProductSearchUseCase) -> None:
        self._use_case = use_case

    async def invoke(self, keyword: str, limit: int = 5) -> dict[str, Any]:
        result = await self._use_case.execute(keyword, limit)
        return {
            "success": result.success,
            "data": result.data,
        }


class TicketCreationTool:
    """客服工單建立工具"""

    name = "ticket_creation"
    description = "建立客服工單，適用於用戶投訴或需要人工處理的問題"

    def __init__(self, use_case: TicketCreationUseCase) -> None:
        self._use_case = use_case

    async def invoke(
        self,
        tenant_id: str,
        subject: str,
        description: str,
        order_id: str = "",
    ) -> dict[str, Any]:
        result = await self._use_case.execute(
            tenant_id=tenant_id,
            subject=subject,
            description=description,
            order_id=order_id,
        )
        return {
            "success": result.success,
            "data": result.data,
        }


class ProductRecommendTool:
    """商品推薦工具 — 搜尋系統 KB 進行商品推薦"""

    name = "product_recommend"
    description = "商品推薦：根據用戶需求搜尋商品目錄，適用於商品推薦、商品比較"

    def __init__(
        self,
        query_rag_use_case: QueryRAGUseCase,
        kb_repository: KnowledgeBaseRepository,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> None:
        self._use_case = query_rag_use_case
        self._kb_repo = kb_repository
        self._top_k = top_k
        self._score_threshold = score_threshold

    async def invoke(self, tenant_id: str, query: str) -> dict[str, Any]:
        system_kbs = await self._kb_repo.find_system_kbs(tenant_id)
        if not system_kbs:
            return {"success": False, "error": "尚未建立商品目錄"}

        kb_ids = [kb.id.value for kb in system_kbs]
        try:
            result = await self._use_case.execute(
                QueryRAGCommand(
                    tenant_id=tenant_id,
                    kb_id=kb_ids[0],
                    query=query,
                    kb_ids=kb_ids,
                    top_k=self._top_k,
                    score_threshold=self._score_threshold,
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
                "answer": "商品目錄中沒有找到相關商品。",
                "sources": [],
            }
