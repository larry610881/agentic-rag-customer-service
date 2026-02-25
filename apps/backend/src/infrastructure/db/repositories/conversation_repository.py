"""SQLAlchemy Conversation Repository 實作"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.repository import ConversationRepository
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.infrastructure.db.models.conversation_model import ConversationModel
from src.infrastructure.db.models.message_model import MessageModel


class SQLAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, conversation: Conversation) -> None:
        existing = await self._session.get(
            ConversationModel, conversation.id.value
        )
        if existing is None:
            model = ConversationModel(
                id=conversation.id.value,
                tenant_id=conversation.tenant_id,
                bot_id=conversation.bot_id,
                created_at=conversation.created_at,
            )
            self._session.add(model)

        for msg in conversation.messages:
            existing_msg = await self._session.get(MessageModel, msg.id.value)
            if existing_msg is None:
                msg_model = MessageModel(
                    id=msg.id.value,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    tool_calls_json=json.dumps(
                        msg.tool_calls, ensure_ascii=False
                    ),
                    created_at=msg.created_at,
                )
                self._session.add(msg_model)

        await self._session.commit()

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
                created_at=r.created_at,
            )
            for r in msg_rows
        ]

        return Conversation(
            id=ConversationId(value=model.id),
            tenant_id=model.tenant_id,
            bot_id=model.bot_id,
            messages=messages,
            created_at=model.created_at,
        )

    async def find_by_tenant(
        self, tenant_id: str, *, bot_id: str | None = None
    ) -> list[Conversation]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.tenant_id == tenant_id)
        )
        if bot_id is not None:
            stmt = stmt.where(ConversationModel.bot_id == bot_id)
        stmt = stmt.order_by(ConversationModel.created_at.desc())
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            Conversation(
                id=ConversationId(value=r.id),
                tenant_id=r.tenant_id,
                bot_id=r.bot_id,
                messages=[],
                created_at=r.created_at,
            )
            for r in rows
        ]
