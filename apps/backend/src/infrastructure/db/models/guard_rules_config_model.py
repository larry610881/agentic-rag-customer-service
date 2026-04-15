from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class GuardRulesConfigModel(Base):
    __tablename__ = "guard_rules_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")
    input_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    output_keywords: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    llm_guard_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_guard_model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    input_guard_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_guard_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    blocked_response: Mapped[str] = mapped_column(
        Text, nullable=False, default="我只能協助您處理客服相關問題。"
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
