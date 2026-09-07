"""BillingSettings ORM Model — Issue #74 平台計價設定（單列 id='default'）"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class BillingSettingsModel(Base):
    __tablename__ = "billing_settings"

    id: Mapped[str] = mapped_column(String(8), primary_key=True, default="default")
    usd_per_point: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0.001")
    )
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
