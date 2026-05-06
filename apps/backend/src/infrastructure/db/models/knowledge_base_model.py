from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class KnowledgeBaseModel(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    kb_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default="user"
    )
    ocr_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="general", server_default="general"
    )
    ocr_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    context_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    classification_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    embedding_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    # Per-KB chunk_strategy override（"" = 走全域 config.chunk_strategy）。
    # 對應 migration: add_chunk_strategy_to_knowledge_bases.sql
    chunk_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )
    # Issue #47 L3：KB-level DM metadata 抽取設定 + 結果儲存
    # 對應 migration: add_kb_dm_metadata.sql
    # dm_metadata_model 空 = 不啟用 KB-level extract（trigger 會 skip）
    # dm_metadata 預設 {} — 由 ExtractKBDMMetadataUseCase 寫入完整 JSON
    dm_metadata_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    dm_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
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
        Index("ix_knowledge_bases_tenant_id", "tenant_id"),
    )
