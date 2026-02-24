"""LangGraphAgentService — 使用 LangGraph StateGraph 處理訊息"""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import Source, TokenUsage
from src.infrastructure.langgraph.agent_graph import build_agent_graph
from src.infrastructure.langgraph.tools import (
    OrderLookupTool,
    ProductSearchTool,
    RAGQueryTool,
    TicketCreationTool,
)


class LangGraphAgentService(AgentService):
    def __init__(
        self,
        llm_service: LLMService,
        rag_tool: RAGQueryTool,
        order_tool: OrderLookupTool,
        product_tool: ProductSearchTool,
        ticket_tool: TicketCreationTool,
    ) -> None:
        self._llm_service = llm_service
        graph = build_agent_graph(
            llm_service, rag_tool, order_tool, product_tool, ticket_tool
        )
        self._compiled = graph.compile()

    async def process_message(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResponse:
        initial_state = {
            "messages": [],
            "user_message": user_message,
            "tenant_id": tenant_id,
            "kb_id": kb_id,
            "current_tool": "",
            "tool_reasoning": "",
            "tool_result": {},
            "final_answer": "",
            "accumulated_usage": {},
        }

        result = await self._compiled.ainvoke(initial_state)

        tool_name = result.get("current_tool", "")
        tool_reasoning = result.get("tool_reasoning", "")
        answer = result.get("final_answer", "")

        # Extract sources from RAG tool results
        sources: list[Source] = []
        tool_result = result.get("tool_result", {})
        if tool_name == "rag_query" and isinstance(tool_result, dict):
            raw_sources = tool_result.get("sources", [])
            sources = [
                Source(
                    document_name=s.get("document_name", ""),
                    content_snippet=s.get("content_snippet", ""),
                    score=s.get("score", 0.0),
                    chunk_id=s.get("chunk_id", ""),
                )
                for s in raw_sources
            ]

        # Convert accumulated_usage dict to TokenUsage
        acc = result.get("accumulated_usage", {})
        usage = (
            TokenUsage(
                model=acc.get("model", "unknown"),
                input_tokens=acc.get("input_tokens", 0),
                output_tokens=acc.get("output_tokens", 0),
                total_tokens=acc.get("total_tokens", 0),
                estimated_cost=acc.get("estimated_cost", 0.0),
            )
            if acc
            else None
        )

        return AgentResponse(
            answer=answer,
            tool_calls=[
                {"tool_name": tool_name, "reasoning": tool_reasoning},
            ],
            sources=sources,
            conversation_id=str(uuid4()),
            usage=usage,
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
        # Stream the answer token by token
        for char in response.answer:
            yield char
        # Yield sources as JSON event
        if response.sources:
            sources_data = [s.to_dict() for s in response.sources]
            yield f"\n[SOURCES]{json.dumps(sources_data, ensure_ascii=False)}"
