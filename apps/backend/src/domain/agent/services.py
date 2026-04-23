"""Agent 服務介面"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from src.domain.agent.entity import AgentResponse
from src.domain.conversation.entity import Message


class AgentService(ABC):
    @abstractmethod
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
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        bot_id: str = "",
    ) -> AgentResponse: ...

    @abstractmethod
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
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
        bot_id: str = "",
    ) -> AsyncIterator[dict[str, Any]]: ...  # pragma: no cover
