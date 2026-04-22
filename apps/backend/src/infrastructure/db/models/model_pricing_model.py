"""ModelPricing ORM Models — S-Pricing.1"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class ModelPricingModel(Base):
    __tablename__ = "model_pricing"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="llm"
    )
    input_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False
    )
    output_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False
    )
    cache_read_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    cache_creation_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    effective_from: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "input_price >= 0 AND output_price >= 0 "
            "AND cache_read_price >= 0 AND cache_creation_price >= 0",
            name="chk_prices_non_negative",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="chk_effective_range",
        ),
        Index(
            "idx_model_pricing_lookup",
            "provider",
            "model_id",
            "effective_from",
        ),
        Index("idx_model_pricing_effective", "effective_from"),
    )


class PricingRecalcAuditModel(Base):
    __tablename__ = "pricing_recalc_audit"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True
    )
    pricing_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("model_pricing.id"),
        nullable=False,
    )
    recalc_from: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    recalc_to: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    affected_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_before_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False
    )
    cost_after_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False
    )
    executed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_pricing_recalc_audit_executed", "executed_at"),
    )
