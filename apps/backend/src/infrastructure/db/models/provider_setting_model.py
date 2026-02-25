from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class ProviderSettingModel(Base):
    __tablename__ = "provider_settings"
    __table_args__ = (
        UniqueConstraint(
            "provider_type", "provider_name", name="uq_provider_type_name"
        ),
        Index("ix_provider_settings_type", "provider_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    models: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    extra_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
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
