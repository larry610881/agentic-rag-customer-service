"""Eval dataset and test case models for prompt optimization."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class EvalDatasetModel(Base):
    __tablename__ = "eval_datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_prompt: Mapped[str] = mapped_column(String(50), nullable=False, default="base_prompt")
    agent_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="router")
    default_assertions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cost_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    include_security: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    test_cases: Mapped[list["EvalTestCaseModel"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_eval_datasets_tenant_id", "tenant_id"),
    )


class EvalTestCaseModel(Base):
    __tablename__ = "eval_test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eval_datasets.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(5), nullable=False, default="P1")
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    conversation_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    assertions: Mapped[list] = mapped_column(JSON, nullable=False)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    dataset: Mapped["EvalDatasetModel"] = relationship(back_populates="test_cases")

    __table_args__ = (
        Index("ix_eval_test_cases_dataset_id", "dataset_id"),
    )
