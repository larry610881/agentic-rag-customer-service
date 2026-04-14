"""Bot Worker DB Model"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class BotWorkerModel(Base):
    __tablename__ = "bot_workers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    system_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    llm_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    llm_model: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    temperature: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1024
    )
    max_tool_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5
    )
    enabled_mcp_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    use_rag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_bot_workers_bot_id", "bot_id"),
    )
