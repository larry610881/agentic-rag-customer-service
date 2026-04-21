"""SQLAlchemy Conversation Repository 實作"""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.conversation_model import ConversationModel
from src.infrastructure.db.models.message_model import MessageModel


class SQLAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, conversation: Conversation) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                ConversationModel, conversation.id.value
            )
            if existing is None:
                model = ConversationModel(
                    id=conversation.id.value,
                    tenant_id=conversation.tenant_id,
                    bot_id=conversation.bot_id,
                    visitor_id=conversation.visitor_id,
                    created_at=conversation.created_at,
                    # S-Gov.6b: 5 個 summary 欄位
                    summary=conversation.summary,
                    message_count=conversation.message_count,
                    summary_message_count=conversation.summary_message_count,
                    last_message_at=conversation.last_message_at,
                    summary_at=conversation.summary_at,
                )
                self._session.add(model)
            else:
                if conversation.visitor_id and not existing.visitor_id:
                    existing.visitor_id = conversation.visitor_id
                # S-Gov.6b: summary 5 欄位允許 update（generate_summary_use_case 會寫）
                # message_count + last_message_at 由 SendMessageUseCase hook 寫
                existing.summary = conversation.summary
                existing.message_count = conversation.message_count
                existing.summary_message_count = (
                    conversation.summary_message_count
                )
                existing.last_message_at = conversation.last_message_at
                existing.summary_at = conversation.summary_at

            if conversation.messages:
                # Bulk check: fetch all existing message IDs in one query
                msg_ids = [msg.id.value for msg in conversation.messages]
                stmt = select(MessageModel.id).where(
                    MessageModel.id.in_(msg_ids)
                )
                result = await self._session.execute(stmt)
                existing_ids = set(result.scalars().all())

                for msg in conversation.messages:
                    if msg.id.value not in existing_ids:
                        msg_model = MessageModel(
                            id=msg.id.value,
                            conversation_id=msg.conversation_id,
                            role=msg.role,
                            content=msg.content,
                            tool_calls_json=json.dumps(
                                msg.tool_calls, ensure_ascii=False
                            ),
                            latency_ms=msg.latency_ms,
                            retrieved_chunks=(
                                json.dumps(
                                    msg.retrieved_chunks, ensure_ascii=False
                                )
                                if msg.retrieved_chunks is not None
                                else None
                            ),
                            structured_content=(
                                json.dumps(
                                    msg.structured_content, ensure_ascii=False
                                )
                                if msg.structured_content is not None
                                else None
                            ),
                            created_at=msg.created_at,
                        )
                        self._session.add(msg_model)

    async def find_by_id(
        self, conversation_id: str
    ) -> Conversation | None:
        model = await self._session.get(ConversationModel, conversation_id)
        if model is None:
            return None

        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
        )
        result = await self._session.execute(stmt)
        msg_rows = result.scalars().all()

        messages = [
            Message(
                id=MessageId(value=r.id),
                conversation_id=r.conversation_id,
                role=r.role,
                content=r.content,
                tool_calls=json.loads(r.tool_calls_json),
                latency_ms=r.latency_ms,
                retrieved_chunks=(
                    json.loads(r.retrieved_chunks)
                    if r.retrieved_chunks is not None
                    else None
                ),
                structured_content=(
                    json.loads(r.structured_content)
                    if r.structured_content is not None
                    else None
                ),
                created_at=r.created_at,
            )
            for r in msg_rows
        ]

        return Conversation(
            id=ConversationId(value=model.id),
            tenant_id=model.tenant_id,
            bot_id=model.bot_id,
            visitor_id=model.visitor_id,
            messages=messages,
            created_at=model.created_at,
            summary=model.summary,
            message_count=model.message_count,
            summary_message_count=model.summary_message_count,
            last_message_at=model.last_message_at,
            summary_at=model.summary_at,
        )

    async def find_by_tenant(
        self,
        tenant_id: str,
        *,
        bot_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Conversation]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.tenant_id == tenant_id)
        )
        if bot_id is not None:
            stmt = stmt.where(ConversationModel.bot_id == bot_id)
        stmt = stmt.order_by(ConversationModel.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            Conversation(
                id=ConversationId(value=r.id),
                tenant_id=r.tenant_id,
                bot_id=r.bot_id,
                messages=[],
                created_at=r.created_at,
                summary=r.summary,
                message_count=r.message_count,
                summary_message_count=r.summary_message_count,
                last_message_at=r.last_message_at,
                summary_at=r.summary_at,
            )
            for r in rows
        ]

    async def count_by_tenant(
        self, tenant_id: str, *, bot_id: str | None = None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(ConversationModel)
            .where(ConversationModel.tenant_id == tenant_id)
        )
        if bot_id is not None:
            stmt = stmt.where(ConversationModel.bot_id == bot_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def find_latest_by_visitor(
        self, visitor_id: str, bot_id: str
    ) -> Conversation | None:
        """Find the most recent conversation for a visitor + bot pair."""
        stmt = (
            select(ConversationModel)
            .where(
                ConversationModel.visitor_id == visitor_id,
                ConversationModel.bot_id == bot_id,
            )
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None

        # Load messages
        msg_stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == model.id)
            .order_by(MessageModel.created_at)
        )
        msg_result = await self._session.execute(msg_stmt)
        msg_rows = msg_result.scalars().all()

        messages = [
            Message(
                id=MessageId(value=r.id),
                conversation_id=r.conversation_id,
                role=r.role,
                content=r.content,
                tool_calls=json.loads(r.tool_calls_json),
                latency_ms=r.latency_ms,
                retrieved_chunks=(
                    json.loads(r.retrieved_chunks)
                    if r.retrieved_chunks is not None
                    else None
                ),
                structured_content=(
                    json.loads(r.structured_content)
                    if r.structured_content is not None
                    else None
                ),
                created_at=r.created_at,
            )
            for r in msg_rows
        ]

        return Conversation(
            id=ConversationId(value=model.id),
            tenant_id=model.tenant_id,
            bot_id=model.bot_id,
            visitor_id=model.visitor_id,
            messages=messages,
            created_at=model.created_at,
            summary=model.summary,
            message_count=model.message_count,
            summary_message_count=model.summary_message_count,
            last_message_at=model.last_message_at,
            summary_at=model.summary_at,
        )

    async def find_conversation_id_by_message(
        self, message_id: str
    ) -> str | None:
        """Look up which conversation a message belongs to."""
        stmt = select(MessageModel.conversation_id).where(
            MessageModel.id == message_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_pending_summary(
        self,
        *,
        idle_minutes: int = 5,
        limit: int = 200,
    ) -> list[str]:
        """S-Gov.6b: 找需要生 summary 的 conversation_id（cron 用）。

        條件（與 partial index ix_conversations_pending_summary 對齊）：
        - last_message_at < NOW() - INTERVAL 'idle_minutes minutes'（閒置）
        - summary IS NULL OR summary_message_count < message_count（pending）
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=idle_minutes)
        stmt = (
            select(ConversationModel.id)
            .where(
                ConversationModel.last_message_at.is_not(None),
                ConversationModel.last_message_at < cutoff,
                or_(
                    ConversationModel.summary.is_(None),
                    ConversationModel.summary_message_count
                    < ConversationModel.message_count,
                ),
            )
            .order_by(ConversationModel.last_message_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_summary_by_keyword(
        self,
        *,
        keyword: str,
        tenant_id: str | None = None,
        bot_id: str | None = None,
        limit: int = 20,
    ) -> list[Conversation]:
        """S-Gov.6b: PG ILIKE 搜尋 summary 欄位（不載入 messages）。"""
        stmt = select(ConversationModel).where(
            ConversationModel.summary.is_not(None),
            ConversationModel.summary.ilike(f"%{keyword}%"),
        )
        if tenant_id is not None:
            stmt = stmt.where(ConversationModel.tenant_id == tenant_id)
        if bot_id is not None:
            stmt = stmt.where(ConversationModel.bot_id == bot_id)
        stmt = stmt.order_by(
            ConversationModel.last_message_at.desc().nulls_last()
        ).limit(limit)
        result = await self._session.execute(stmt)
        return [
            Conversation(
                id=ConversationId(value=r.id),
                tenant_id=r.tenant_id,
                bot_id=r.bot_id,
                visitor_id=r.visitor_id,
                messages=[],
                created_at=r.created_at,
                summary=r.summary,
                message_count=r.message_count,
                summary_message_count=r.summary_message_count,
                last_message_at=r.last_message_at,
                summary_at=r.summary_at,
            )
            for r in result.scalars().all()
        ]

    async def find_by_ids(
        self, conversation_ids: list[str]
    ) -> list[Conversation]:
        """S-Gov.6b: 批次取 conversation header（給 semantic search hydrate 用）。"""
        if not conversation_ids:
            return []
        stmt = select(ConversationModel).where(
            ConversationModel.id.in_(conversation_ids)
        )
        result = await self._session.execute(stmt)
        return [
            Conversation(
                id=ConversationId(value=r.id),
                tenant_id=r.tenant_id,
                bot_id=r.bot_id,
                visitor_id=r.visitor_id,
                messages=[],
                created_at=r.created_at,
                summary=r.summary,
                message_count=r.message_count,
                summary_message_count=r.summary_message_count,
                last_message_at=r.last_message_at,
                summary_at=r.summary_at,
            )
            for r in result.scalars().all()
        ]
