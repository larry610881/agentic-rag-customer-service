from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class BotModel(Base):
    __tablename__ = "bots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled_tools: Mapped[list] = mapped_column(
        JSON, nullable=False, default=lambda: ["rag_query"]
    )
    line_channel_secret: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    line_channel_access_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    history_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    frequency_penalty: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    reasoning_effort: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium"
    )
    rag_top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rag_score_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.3
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
        Index("ix_bots_tenant_id", "tenant_id"),
    )
