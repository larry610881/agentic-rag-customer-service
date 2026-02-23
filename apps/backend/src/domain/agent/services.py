"""Agent 服務介面"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

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
    ) -> AgentResponse: ...

    @abstractmethod
    async def process_message_stream(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
    ) -> AsyncIterator[str]: ...  # pragma: no cover
