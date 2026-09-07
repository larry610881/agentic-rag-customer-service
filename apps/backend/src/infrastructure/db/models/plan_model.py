"""Plan ORM Model — S-Token-Gov.1 方案模板"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
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
    # Issue #74：雙軌計價 + 額度用盡策略
    billing_mode: Mapped[str] = mapped_column(
        String(10), nullable=False, default="token", server_default="token"
    )
    monthly_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    addon_pack_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    default_category_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False, default=Decimal("1"), server_default="1"
    )
    exhaustion_policy: Mapped[str] = mapped_column(
        String(12), nullable=False, default="auto_topup", server_default="auto_topup"
    )
    tenant_may_change_policy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    auto_topup_monthly_cap: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    grace_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    block_message: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
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
