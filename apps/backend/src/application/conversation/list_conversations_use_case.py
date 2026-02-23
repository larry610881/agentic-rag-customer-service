"""列出租戶對話用例"""

from src.domain.conversation.entity import Conversation
from src.domain.conversation.repository import ConversationRepository


class ListConversationsUseCase:
    def __init__(
        self, conversation_repository: ConversationRepository
    ) -> None:
        self._repo = conversation_repository

    async def execute(self, tenant_id: str) -> list[Conversation]:
        return await self._repo.find_by_tenant(tenant_id)
