"""TokenLedger ORM Model — S-Token-Gov.2"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class TokenLedgerModel(Base):
    __tablename__ = "token_ledgers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    cycle_year_month: Mapped[str] = mapped_column(
        String(7), nullable=False
    )  # "YYYY-MM"
    plan_name: Mapped[str] = mapped_column(String(50), nullable=False)
    base_total: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    base_remaining: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    addon_remaining: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )  # 可為負（軟上限）
    total_used_in_cycle: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
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

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "cycle_year_month", name="uq_ledger_tenant_cycle"
        ),
        Index("ix_token_ledgers_tenant_cycle", "tenant_id", "cycle_year_month"),
    )
