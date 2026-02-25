"""列表回饋 Use Case"""

from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository


class ListFeedbackUseCase:
    def __init__(self, feedback_repository: FeedbackRepository):
        self._feedback_repo = feedback_repository

    async def execute(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[Feedback]:
        return await self._feedback_repo.find_by_tenant(
            tenant_id, limit=limit, offset=offset
        )

    async def execute_by_conversation(
        self, conversation_id: str, tenant_id: str
    ) -> list[Feedback]:
        feedbacks = await self._feedback_repo.find_by_conversation(
            conversation_id
        )
        return [f for f in feedbacks if f.tenant_id == tenant_id]

    async def update_tags(
        self, feedback_id: str, tags: list[str]
    ) -> None:
        # feedback_id is actually used as message_id lookup
        await self._feedback_repo.update_tags(feedback_id, tags)
