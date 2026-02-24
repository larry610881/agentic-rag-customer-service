"""FakeAgentService — SupervisorAgentService wrapper（向後相容）"""

from collections.abc import AsyncIterator
from typing import Any

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Message
from src.infrastructure.langgraph.supervisor_agent_service import (
    SupervisorAgentService,
)
from src.infrastructure.langgraph.workers.fake_main_worker import FakeMainWorker


class FakeAgentService(AgentService):
    """向後相容 wrapper，委派給 SupervisorAgentService"""

    def __init__(self) -> None:
        self._supervisor = SupervisorAgentService(
            workers=[FakeMainWorker()]
        )

    async def process_message(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResponse:
        return await self._supervisor.process_message(
            tenant_id, kb_id, user_message, history, metadata=metadata
        )

    async def process_message_stream(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
    ) -> AsyncIterator[str]:
        async for chunk in self._supervisor.process_message_stream(
            tenant_id, kb_id, user_message, history
        ):
            yield chunk
