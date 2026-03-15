from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class MemoryFactModel(Base):
    __tablename__ = "memory_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("visitor_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    memory_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="long_term", server_default="long_term"
    )
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, default="custom", server_default="custom"
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_conversation_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
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
        UniqueConstraint("profile_id", "key", name="uq_memory_fact_key"),
        Index("ix_memory_facts_profile", "profile_id"),
        Index("ix_memory_facts_tenant", "tenant_id"),
        Index("ix_memory_facts_profile_type", "profile_id", "memory_type"),
    )
