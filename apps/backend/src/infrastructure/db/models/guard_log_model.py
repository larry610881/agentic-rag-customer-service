from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class GuardLogModel(Base):
    __tablename__ = "guard_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    log_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_matched: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    user_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_guard_logs_tenant_id", "tenant_id"),
        Index("ix_guard_logs_created_at", "created_at"),
    )
