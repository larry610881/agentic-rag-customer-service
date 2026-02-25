"""對話 ORM Model"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_conversations_tenant_id", "tenant_id"),
        Index("ix_conversations_tenant_bot", "tenant_id", "bot_id"),
    )
