"""BillingTransaction ORM Model — S-Token-Gov.3"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class BillingTransactionModel(Base):
    __tablename__ = "billing_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    ledger_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("token_ledgers.id", ondelete="CASCADE"),
        nullable=False,
    )
    cycle_year_month: Mapped[str] = mapped_column(
        String(7), nullable=False
    )  # snapshot
    plan_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # snapshot
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    addon_tokens_added: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    amount_currency: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # snapshot
    amount_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )  # snapshot
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "ix_billing_transactions_tenant_cycle",
            "tenant_id",
            "cycle_year_month",
        ),
        Index("ix_billing_transactions_created", "created_at"),
    )
