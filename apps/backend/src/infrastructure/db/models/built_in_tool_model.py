"""Built-in tool SQLAlchemy model (mirror of McpServerModel scope pattern)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class BuiltInToolModel(Base):
    __tablename__ = "built_in_tools"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(
        String(2000), nullable=False, default=""
    )
    requires_kb: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="global"
    )
    tenant_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
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
