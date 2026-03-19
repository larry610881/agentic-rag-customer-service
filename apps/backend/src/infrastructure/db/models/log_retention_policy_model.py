from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class LogRetentionPolicyModel(Base):
    __tablename__ = "log_retention_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="system")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    cleanup_hour: Mapped[int] = mapped_column(Integer, default=3)
    cleanup_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_cleanup_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    deleted_count_last: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
