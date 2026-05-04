from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kb_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_content: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True, default=None
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000), nullable=False, default=""
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, default=None
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    chunk_count: Mapped[int] = mapped_column(nullable=False, default=0)
    avg_chunk_length: Mapped[int] = mapped_column(nullable=False, default=0)
    min_chunk_length: Mapped[int] = mapped_column(nullable=False, default=0)
    max_chunk_length: Mapped[int] = mapped_column(nullable=False, default=0)
    quality_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    quality_issues: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    # Issue #44: External producer reference. Populated by bulk ingest from
    # incoming metadata; empty string for documents uploaded via the
    # interactive single-file UI.
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    source_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default=""
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
        Index("ix_documents_kb_id", "kb_id"),
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_parent_id", "parent_id"),
        # Issue #44: bulk ingest dedup walks (kb_id, source, source_id) when
        # the upstream producer re-pushes the same source record.
        Index("ix_documents_kb_source", "kb_id", "source", "source_id"),
    )
