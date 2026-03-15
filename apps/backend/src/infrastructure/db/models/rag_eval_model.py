from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class RAGEvalModel(Base):
    __tablename__ = "rag_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    eval_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    dimensions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_used: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_rag_evaluations_tenant_id", "tenant_id"),
        Index("ix_rag_evaluations_created_at", "created_at"),
        Index("ix_rag_evaluations_layer", "layer"),
    )
