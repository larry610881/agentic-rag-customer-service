"""提交回饋 Use Case"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.conversation.entity import Conversation
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
    # #102：訪客通路（widget）限定對話必須屬於該 bot 與該訪客。
    # None = 不限定（已登入的租戶使用者，已由 tenant_id 範圍保護）。
    bot_id: str | None = None
    visitor_ids: tuple[str, ...] | None = None


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
        if not _visible_to_caller(conversation, command):
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


def _visible_to_caller(
    conversation: Conversation, command: SubmitFeedbackCommand
) -> bool:
    """訪客通路的對話歸屬：同 bot、且對話的 visitor_id 是呼叫者的身分之一。"""
    if command.bot_id is not None and conversation.bot_id != command.bot_id:
        return False
    if command.visitor_ids is not None:
        return bool(conversation.visitor_id) and (
            conversation.visitor_id in command.visitor_ids
        )
    return True

