"""QuotaAlertLog ORM Model — S-Token-Gov.3"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class QuotaAlertLogModel(Base):
    __tablename__ = "quota_alert_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    cycle_year_month: Mapped[str] = mapped_column(
        String(7), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    used_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_to_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "cycle_year_month",
            "alert_type",
            name="uq_quota_alert_unique",
        ),
        Index("ix_quota_alert_logs_created", "created_at"),
    )
