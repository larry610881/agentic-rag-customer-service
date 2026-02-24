"""Agent 服務介面"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from src.domain.agent.entity import AgentResponse
from src.domain.agent.value_objects import SentimentResult
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
    ) -> AgentResponse: ...

    @abstractmethod
    async def process_message_stream(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
    ) -> AsyncIterator[str]: ...  # pragma: no cover


class SentimentService(ABC):
    @abstractmethod
    async def analyze(self, text: str) -> SentimentResult: ...
