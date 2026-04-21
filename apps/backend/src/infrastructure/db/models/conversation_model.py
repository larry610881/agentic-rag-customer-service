"""對話 ORM Model"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    visitor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # S-Gov.6b: LLM 摘要 + race-safe 觸發追蹤
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    summary_message_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )
    summary_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )

    __table_args__ = (
        Index("ix_conversations_tenant_id", "tenant_id"),
        Index("ix_conversations_tenant_bot", "tenant_id", "bot_id"),
        Index("ix_conversations_visitor_bot", "visitor_id", "bot_id"),
        # S-Gov.6b partial index 已在 migration 建立（pending summary cron 用）
    )
