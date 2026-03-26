"""SQLAlchemy Feedback Repository 實作"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.conversation.feedback_analysis_vo import (
    DailyFeedbackStat,
    RetrievalQualityRecord,
    TagCount,
)
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.feedback_model import FeedbackModel
from src.infrastructure.db.models.message_model import MessageModel


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
            retrieval_quality=model.retrieval_quality,
            created_at=model.created_at,
        )

    async def save(self, feedback: Feedback) -> None:
        async with atomic(self._session):
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
                retrieval_quality=feedback.retrieval_quality,
                created_at=feedback.created_at,
            )
            self._session.add(model)

    async def update(self, feedback: Feedback) -> None:
        async with atomic(self._session):
            stmt = select(FeedbackModel).where(
                FeedbackModel.id == feedback.id.value
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return
            model.rating = feedback.rating.value
            model.comment = feedback.comment
            model.tags = json.dumps(feedback.tags, ensure_ascii=False)
            model.retrieval_quality = feedback.retrieval_quality

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

    async def update_tags(
        self, message_id: str, tags: list[str]
    ) -> None:
        async with atomic(self._session):
            stmt = select(FeedbackModel).where(
                FeedbackModel.message_id == message_id
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            if model is None:
                return
            existing_tags: list[str] = json.loads(model.tags)
            merged = list(dict.fromkeys(existing_tags + tags))
            model.tags = json.dumps(merged, ensure_ascii=False)

    async def get_daily_trend(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DailyFeedbackStat]:
        stmt = (
            select(
                func.date(FeedbackModel.created_at).label("dt"),
                func.count().label("total"),
                func.count()
                .filter(FeedbackModel.rating == Rating.THUMBS_UP.value)
                .label("positive"),
                func.count()
                .filter(FeedbackModel.rating == Rating.THUMBS_DOWN.value)
                .label("negative"),
            )
            .where(FeedbackModel.tenant_id == tenant_id)
            .group_by(func.date(FeedbackModel.created_at))
            .order_by(func.date(FeedbackModel.created_at))
        )
        if start_date:
            stmt = stmt.where(FeedbackModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(FeedbackModel.created_at < end_date)
        result = await self._session.execute(stmt)
        rows = result.all()
        return [
            DailyFeedbackStat(
                date=r.dt,
                total=r.total,
                positive=r.positive,
                negative=r.negative,
                satisfaction_pct=(
                    round(r.positive * 100.0 / r.total, 1) if r.total else 0.0
                ),
            )
            for r in rows
        ]

    async def get_top_tags(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[TagCount]:
        stmt = (
            select(FeedbackModel.tags)
            .where(
                FeedbackModel.tenant_id == tenant_id,
                FeedbackModel.rating == Rating.THUMBS_DOWN.value,
            )
        )
        if start_date:
            stmt = stmt.where(FeedbackModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(FeedbackModel.created_at < end_date)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        tag_counts: dict[str, int] = {}
        for tags_json in rows:
            tags: list[str] = json.loads(tags_json)
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        return [TagCount(tag=t, count=c) for t, c in sorted_tags[:limit]]

    async def count_negative(
        self, tenant_id: str, days: int = 30
    ) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(func.count())
            .select_from(FeedbackModel)
            .where(
                FeedbackModel.tenant_id == tenant_id,
                FeedbackModel.rating == Rating.THUMBS_DOWN.value,
                FeedbackModel.created_at >= since,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_negative_with_context(
        self, tenant_id: str, days: int = 30, limit: int = 20, offset: int = 0
    ) -> list[RetrievalQualityRecord]:
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Step 1: Fetch feedback rows
        stmt = (
            select(
                FeedbackModel.message_id,
                FeedbackModel.rating,
                FeedbackModel.comment,
                FeedbackModel.created_at,
            )
            .where(
                FeedbackModel.tenant_id == tenant_id,
                FeedbackModel.rating == Rating.THUMBS_DOWN.value,
                FeedbackModel.created_at >= since,
            )
            .order_by(FeedbackModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        feedback_rows = result.all()

        if not feedback_rows:
            return []

        # Step 2: Bulk fetch all assistant messages
        message_ids = [row.message_id for row in feedback_rows]
        asst_stmt = select(MessageModel).where(
            MessageModel.id.in_(message_ids)
        )
        asst_result = await self._session.execute(asst_stmt)
        asst_map = {
            m.id: m for m in asst_result.scalars().all()
        }

        # Step 3: Bulk fetch user messages for related conversations
        conversation_ids = list({
            m.conversation_id for m in asst_map.values()
        })
        if conversation_ids:
            user_stmt = (
                select(MessageModel)
                .where(
                    MessageModel.conversation_id.in_(conversation_ids),
                    MessageModel.role == "user",
                )
                .order_by(
                    MessageModel.conversation_id,
                    MessageModel.created_at.desc(),
                )
            )
            user_result = await self._session.execute(user_stmt)
            user_by_conv: dict[str, list[MessageModel]] = defaultdict(list)
            for u in user_result.scalars().all():
                user_by_conv[u.conversation_id].append(u)
        else:
            user_by_conv = {}

        # Step 4: Assemble records (Python-side matching)
        records: list[RetrievalQualityRecord] = []
        for row in feedback_rows:
            asst_msg = asst_map.get(row.message_id)
            if asst_msg is None:
                continue

            # Find nearest preceding user message in same conversation
            user_msg = None
            for u in user_by_conv.get(asst_msg.conversation_id, []):
                if u.created_at < asst_msg.created_at:
                    user_msg = u
                    break  # already sorted desc, first match is nearest

            retrieved = (
                json.loads(asst_msg.retrieved_chunks)
                if asst_msg.retrieved_chunks
                else []
            )

            records.append(
                RetrievalQualityRecord(
                    user_question=user_msg.content if user_msg else "",
                    assistant_answer=asst_msg.content,
                    retrieved_chunks=retrieved,
                    rating=row.rating,
                    comment=row.comment,
                    created_at=row.created_at,
                )
            )
        return records

    async def find_by_date_range(
        self, tenant_id: str, start: datetime, end: datetime
    ) -> list[Feedback]:
        stmt = (
            select(FeedbackModel)
            .where(
                FeedbackModel.tenant_id == tenant_id,
                FeedbackModel.created_at >= start,
                FeedbackModel.created_at <= end,
            )
            .order_by(FeedbackModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def delete_before_date(
        self, tenant_id: str, before: datetime
    ) -> int:
        async with atomic(self._session):
            stmt = (
                delete(FeedbackModel)
                .where(
                    FeedbackModel.tenant_id == tenant_id,
                    FeedbackModel.created_at < before,
                )
            )
            result = await self._session.execute(stmt)
            return result.rowcount
