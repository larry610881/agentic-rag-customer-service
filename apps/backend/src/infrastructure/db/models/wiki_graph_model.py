"""Wiki Graph ORM model — JSONB storage for wiki BC."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class WikiGraphModel(Base):
    __tablename__ = "wiki_graphs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    bot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
    )
    kb_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    nodes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    edges: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    backlinks: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    clusters: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    wiki_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    compiled_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
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
        UniqueConstraint("bot_id", name="ux_wiki_graphs_bot_id"),
        Index("ix_wiki_graphs_tenant_id", "tenant_id"),
        Index("ix_wiki_graphs_status", "status"),
    )
