"""SQLAlchemy Feedback Repository 實作"""

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.infrastructure.db.models.feedback_model import FeedbackModel


class SQLAlchemyFeedbackRepository(FeedbackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: FeedbackModel) -> Feedback:
        return Feedback(
            id=FeedbackId(value=model.id),
            tenant_id=model.tenant_id,
            conversation_id=model.conversation_id,
            message_id=model.message_id,
            user_id=model.user_id,
            channel=Channel(model.channel),
            rating=Rating(model.rating),
            comment=model.comment,
            tags=json.loads(model.tags),
            created_at=model.created_at,
        )

    async def save(self, feedback: Feedback) -> None:
        model = FeedbackModel(
            id=feedback.id.value,
            tenant_id=feedback.tenant_id,
            conversation_id=feedback.conversation_id,
            message_id=feedback.message_id,
            user_id=feedback.user_id,
            channel=feedback.channel.value,
            rating=feedback.rating.value,
            comment=feedback.comment,
            tags=json.dumps(feedback.tags, ensure_ascii=False),
            created_at=feedback.created_at,
        )
        self._session.add(model)
        await self._session.commit()

    async def find_by_message_id(self, message_id: str) -> Feedback | None:
        stmt = select(FeedbackModel).where(
            FeedbackModel.message_id == message_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_tenant(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[Feedback]:
        stmt = (
            select(FeedbackModel)
            .where(FeedbackModel.tenant_id == tenant_id)
            .order_by(FeedbackModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def find_by_conversation(
        self, conversation_id: str
    ) -> list[Feedback]:
        stmt = (
            select(FeedbackModel)
            .where(FeedbackModel.conversation_id == conversation_id)
            .order_by(FeedbackModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def count_by_tenant_and_rating(
        self, tenant_id: str, rating: Rating | None = None
    ) -> int:
        stmt = select(func.count()).select_from(FeedbackModel).where(
            FeedbackModel.tenant_id == tenant_id
        )
        if rating is not None:
            stmt = stmt.where(FeedbackModel.rating == rating.value)
        result = await self._session.execute(stmt)
        return result.scalar_one()
