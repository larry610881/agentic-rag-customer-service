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

        # message 必須屬於這個 conversation：否則可在他租戶訊息上先佔用回饋
        # （message_id 唯一），或把回饋掛到別的對話。與上面同一個 404，不透露訊息存在。
        if not any(m.id.value == command.message_id for m in conversation.messages):
            raise EntityNotFoundError("Conversation", command.conversation_id)

        existing = await self._feedback_repo.find_by_message_id(
            command.message_id
        )

        # find_by_message_id 不分租戶：他租戶訊息上的既有回饋不可被改寫；
        # 與「對話不屬於本租戶」同一個 404，不透露該訊息存在
        if existing is not None and existing.tenant_id != command.tenant_id:
            raise EntityNotFoundError("Conversation", command.conversation_id)

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
