"""Agent Execution Trace DB Model — 記錄完整 Agent 編排鏈路"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class AgentExecutionTraceModel(Base):
    __tablename__ = "agent_execution_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    agent_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )
    nodes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_tokens: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_agent_exec_traces_tenant_id", "tenant_id"),
        Index("ix_agent_exec_traces_created_at", "created_at"),
        Index("ix_agent_exec_traces_conversation_id", "conversation_id"),
    )
