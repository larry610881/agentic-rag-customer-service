"""Token Usage Record ORM Model"""

from datetime import datetime, timezone

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class UsageRecordModel(Base):
    __tablename__ = "token_usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=""
    )
    model: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    estimated_cost: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_token_usage_records_tenant_created", "tenant_id", "created_at"),
    )
