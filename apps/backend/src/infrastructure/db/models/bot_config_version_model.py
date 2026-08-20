from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class BotConfigVersionModel(Base):
    """Bot 設定版本（append-only，config as commit）— spec §13.2"""

    __tablename__ = "bot_config_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    snapshot_schema: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    changed_fields: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    source_run_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    gate_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    gate_verdict: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    author_user_id: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("bot_id", "version_no", name="uq_bcv_bot_version"),
        Index("ix_bcv_bot_created", "bot_id", "created_at"),
        Index("ix_bcv_tenant", "tenant_id"),
        # partial unique index（is_current 唯一）由 migration SQL 建立：
        # CREATE UNIQUE INDEX ix_bcv_current ON bot_config_versions (bot_id)
        # WHERE is_current
    )
