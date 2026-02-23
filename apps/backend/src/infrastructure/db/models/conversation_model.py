"""對話 ORM Model"""

from datetime import datetime, timezone

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_conversations_tenant_id", "tenant_id"),
    )
