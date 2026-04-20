"""Plan ORM Model — S-Token-Gov.1 方案模板"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class PlanModel(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    base_monthly_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    addon_pack_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    base_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    addon_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="TWD"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
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

    __table_args__ = (Index("ix_plans_active", "is_active"),)
