from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class SystemPromptConfigModel(Base):
    __tablename__ = "system_prompt_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")
    base_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    router_mode_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    react_mode_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
