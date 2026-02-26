from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class RateLimitConfigModel(Base):
    __tablename__ = "rate_limit_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    endpoint_group: Mapped[str] = mapped_column(String(20), nullable=False)
    requests_per_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200
    )
    burst_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=250
    )
    per_user_requests_per_minute: Mapped[int | None] = mapped_column(
        Integer, nullable=True
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
        UniqueConstraint("tenant_id", "endpoint_group", name="uq_rl_tenant_group"),
        Index("ix_rl_configs_tenant_id", "tenant_id"),
    )
