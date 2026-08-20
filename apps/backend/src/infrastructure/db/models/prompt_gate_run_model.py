from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class PromptGateRunModel(Base):
    """閘門驗證 run（Issue #54 Phase C，spec §3.4）"""

    __tablename__ = "prompt_gate_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bot_config_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default="queued"
    )
    verdict: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fail_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    dataset_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    repeats: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    soft_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.8, server_default="0.8"
    )
    total_cases: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hard_failed_cases: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    soft_pass_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    unstable_cases: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    est_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    output_tokens: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TZDateTime, nullable=True
    )

    __table_args__ = (
        Index("ix_pgr_bot_created", "bot_id", "created_at"),
        Index("ix_pgr_tenant", "tenant_id"),
    )
