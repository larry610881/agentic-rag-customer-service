from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class RAGTraceModel(Base):
    __tablename__ = "rag_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    query: Mapped[str] = mapped_column(String(2000), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_rag_traces_tenant_id", "tenant_id"),
        Index("ix_rag_traces_created_at", "created_at"),
    )
