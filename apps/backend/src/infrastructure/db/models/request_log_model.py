from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class RequestLogModel(Base):
    __tablename__ = "request_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_request_logs_created_at", "created_at"),
        Index("ix_request_logs_path", "path"),
        Index("ix_request_logs_tenant_id", "tenant_id"),
    )
