from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class McpServerModel(Base):
    __tablename__ = "mcp_server_registrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    transport: Mapped[str] = mapped_column(String(10), nullable=False, default="http")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    command: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    args: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required_env: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    available_tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    tenant_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
