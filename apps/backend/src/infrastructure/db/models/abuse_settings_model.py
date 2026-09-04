from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class AbuseSettingsModel(Base):
    """Issue #68 P7c：異常控管設定（platform / profile / tenant 三種 scope）。"""

    __tablename__ = "abuse_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    overrides: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("scope_kind", "scope_id", name="uq_abuse_settings_scope"),
    )
