"""Token Usage Record ORM Model"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


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
    # Token-Gov.6: total_tokens 欄位已刪除（與 4 個 raw 欄位重複儲存）
    # SUM query 動態計算：input + output + cache_read + cache_creation
    estimated_cost: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    cache_read_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cache_creation_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    bot_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # S-Pricing.1: 若 row 曾被回溯重算，記錄重算時間戳（查月報可識別被動過的 row）
    cost_recalc_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )

    __table_args__ = (
        Index("ix_token_usage_records_tenant_created", "tenant_id", "created_at"),
        Index("ix_token_usage_records_message_id", "message_id"),
        Index("ix_token_usage_records_tenant_bot_created", "tenant_id", "bot_id", "created_at"),
    )
