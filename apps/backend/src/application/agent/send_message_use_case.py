"""發送訊息用例 — 委託 AgentService 處理，支援對話記憶"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.repository import ConversationRepository

_REFUND_METADATA_MARKER = "__refund_metadata"


@dataclass(frozen=True)
class SendMessageCommand:
    tenant_id: str
    kb_id: str
    message: str
    conversation_id: str | None = None


class SendMessageUseCase:
    def __init__(
        self,
        agent_service: AgentService,
        conversation_repository: ConversationRepository,
    ) -> None:
        self._agent_service = agent_service
        self._conversation_repo = conversation_repository

    async def execute(self, command: SendMessageCommand) -> AgentResponse:
        conversation = await self._load_or_create_conversation(command)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)

        response = await self._agent_service.process_message(
            tenant_id=command.tenant_id,
            kb_id=command.kb_id,
            user_message=command.message,
            history=history,
            metadata=metadata,
        )

        tool_calls_to_save = response.tool_calls[:]
        if response.refund_step:
            tool_calls_to_save.append(
                {
                    "tool_name": _REFUND_METADATA_MARKER,
                    "refund_step": response.refund_step,
                }
            )

        conversation.add_message("user", command.message)
        conversation.add_message(
            "assistant",
            response.answer,
            tool_calls=tool_calls_to_save,
        )
        await self._conversation_repo.save(conversation)

        response.conversation_id = conversation.id.value
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

    async def _load_or_create_conversation(
        self, command: SendMessageCommand
    ) -> Conversation:
        if command.conversation_id:
            existing = await self._conversation_repo.find_by_id(
                command.conversation_id
            )
            if existing is not None:
                return existing

        return Conversation(tenant_id=command.tenant_id)

    @staticmethod
    def _extract_metadata(conversation: Conversation) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for msg in reversed(conversation.messages):
            if msg.role == "assistant":
                for tc in msg.tool_calls:
                    if tc.get("tool_name") == _REFUND_METADATA_MARKER:
                        refund_step = tc.get("refund_step")
                        if refund_step:
                            metadata["refund_step"] = refund_step
                break
        return metadata
