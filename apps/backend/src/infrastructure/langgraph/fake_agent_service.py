"""FakeAgentService — 關鍵字匹配路由，用於測試與開發"""

import re
from collections.abc import AsyncIterator
from uuid import uuid4

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message
from src.domain.rag.value_objects import Source, TokenUsage

# 關鍵字路由規則
_ORDER_KEYWORDS = re.compile(r"訂單|order|ORD-|ord-|物流|配送|送達|到哪")
_PRODUCT_KEYWORDS = re.compile(r"商品|產品|product|搜尋|推薦|電子")
_TICKET_KEYWORDS = re.compile(r"投訴|客訴|抱怨|工單|ticket|申訴|問題")


class FakeAgentService(AgentService):
    """不依賴 LangGraph 的假 Agent，關鍵字匹配路由"""

    async def process_message(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
    ) -> AgentResponse:
        tool_name, reasoning = self._route(user_message)
        answer, sources = self._generate_response(tool_name, user_message)

        return AgentResponse(
            answer=answer,
            tool_calls=[
                {"tool_name": tool_name, "reasoning": reasoning},
            ],
            sources=sources,
            conversation_id=str(uuid4()),
            usage=TokenUsage.zero("fake"),
        )

    async def process_message_stream(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
    ) -> AsyncIterator[str]:
        response = await self.process_message(
            tenant_id, kb_id, user_message, history
        )
        for char in response.answer:
            yield char

    def _route(self, message: str) -> tuple[str, str]:
        if _ORDER_KEYWORDS.search(message):
            return "order_lookup", "用戶查詢訂單狀態"
        if _TICKET_KEYWORDS.search(message):
            return "ticket_creation", "用戶需要建立客服工單"
        if _PRODUCT_KEYWORDS.search(message):
            return "product_search", "用戶搜尋商品"
        return "rag_query", "用戶詢問知識型問題"

    def _generate_response(
        self, tool_name: str, message: str
    ) -> tuple[str, list[Source]]:
        if tool_name == "order_lookup":
            return (
                "您的訂單目前狀態為：已出貨，預計送達日期為 2024-01-20。",
                [],
            )
        if tool_name == "product_search":
            return (
                "為您找到以下相關商品：電子產品類別共有 3 件商品。",
                [],
            )
        if tool_name == "ticket_creation":
            return (
                "已為您建立客服工單，工單編號為 TK-001，我們會盡快處理您的問題。",
                [],
            )
        # rag_query
        return (
            "根據知識庫：退貨政策為 30 天內可退貨，請保持商品完整。",
            [
                Source(
                    document_name="退貨政策.txt",
                    content_snippet="退貨政策為 30 天內可退貨",
                    score=0.9,
                    chunk_id="chunk-fake-1",
                ),
            ],
        )
