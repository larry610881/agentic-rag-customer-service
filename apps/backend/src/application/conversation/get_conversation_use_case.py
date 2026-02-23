"""取得單一對話用例"""

from src.domain.conversation.entity import Conversation
from src.domain.conversation.repository import ConversationRepository


class GetConversationUseCase:
    def __init__(
        self, conversation_repository: ConversationRepository
    ) -> None:
        self._repo = conversation_repository

    async def execute(self, conversation_id: str) -> Conversation | None:
        return await self._repo.find_by_id(conversation_id)
