"""提交回饋 Use Case"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.domain.conversation.repository import ConversationRepository
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class SubmitFeedbackCommand:
    tenant_id: str
    conversation_id: str
    message_id: str
    channel: str
    rating: str
    user_id: str | None = None
    comment: str | None = None
    tags: list[str] = field(default_factory=list)


class SubmitFeedbackUseCase:
    def __init__(
        self,
        feedback_repository: FeedbackRepository,
        conversation_repository: ConversationRepository,
    ):
        self._feedback_repo = feedback_repository
        self._conversation_repo = conversation_repository

    async def execute(self, command: SubmitFeedbackCommand) -> Feedback:
        conversation = await self._conversation_repo.find_by_id(
            command.conversation_id
        )
        if conversation is None or conversation.tenant_id != command.tenant_id:
            raise EntityNotFoundError("Conversation", command.conversation_id)

        existing = await self._feedback_repo.find_by_message_id(
            command.message_id
        )

        # E8: upsert — 已有回饋則更新（改變心意）
        if existing is not None:
            existing.rating = Rating(command.rating)
            existing.comment = command.comment
            existing.tags = list(command.tags) if command.tags else existing.tags
            await self._feedback_repo.update(existing)
            return existing

        feedback = Feedback(
            id=FeedbackId(),
            tenant_id=command.tenant_id,
            conversation_id=command.conversation_id,
            message_id=command.message_id,
            user_id=command.user_id,
            channel=Channel(command.channel),
            rating=Rating(command.rating),
            comment=command.comment,
            tags=list(command.tags),
            created_at=datetime.now(timezone.utc),
        )

        await self._feedback_repo.save(feedback)
        return feedback
