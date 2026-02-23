"""發送訊息用例 — 委託 AgentService 處理"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService


@dataclass(frozen=True)
class SendMessageCommand:
    tenant_id: str
    kb_id: str
    message: str
    conversation_id: str | None = None


class SendMessageUseCase:
    def __init__(self, agent_service: AgentService) -> None:
        self._agent_service = agent_service

    async def execute(self, command: SendMessageCommand) -> AgentResponse:
        response = await self._agent_service.process_message(
            tenant_id=command.tenant_id,
            kb_id=command.kb_id,
            user_message=command.message,
        )
        return response

    async def execute_stream(
        self, command: SendMessageCommand
    ) -> AsyncIterator[str]:
        async for chunk in self._agent_service.process_message_stream(
            tenant_id=command.tenant_id,
            kb_id=command.kb_id,
            user_message=command.message,
        ):
            yield chunk
