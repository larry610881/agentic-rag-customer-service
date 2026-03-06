"""ReActAgentService — placeholder for ReAct (RAG + MCP Tools) agent mode.

This service implements the AgentService interface but raises
NotImplementedError for all methods. It will be fully implemented
when ReAct mode is built out with MCP client integration.
"""

from collections.abc import AsyncIterator
from typing import Any

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message
from src.domain.rag.services import LLMService
from src.infrastructure.langgraph.tools import RAGQueryTool


class ReActAgentService(AgentService):
    def __init__(
        self,
        llm_service: LLMService,
        rag_tool: RAGQueryTool,
    ) -> None:
        self._llm_service = llm_service
        self._rag_tool = rag_tool

    async def process_message(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        kb_ids: list[str] | None = None,
        system_prompt: str | None = None,
        llm_params: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
        enabled_tools: list[str] | None = None,
        rag_top_k: int | None = None,
        rag_score_threshold: float | None = None,
    ) -> AgentResponse:
        raise NotImplementedError(
            "ReAct agent mode is not yet implemented"
        )

    async def process_message_stream(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        kb_ids: list[str] | None = None,
        system_prompt: str | None = None,
        llm_params: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
        enabled_tools: list[str] | None = None,
        rag_top_k: int | None = None,
        rag_score_threshold: float | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        raise NotImplementedError(
            "ReAct agent mode is not yet implemented"
        )
        yield  # pragma: no cover — make this an async generator
