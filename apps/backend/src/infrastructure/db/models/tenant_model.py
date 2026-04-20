from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base

TZDateTime = DateTime(timezone=True)


class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="starter")
    monthly_token_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    # S-Token-Gov.2: NULL=全計入；list=只計入列表內的；[]=全不計入
    included_categories: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    default_ocr_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    default_context_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    default_classification_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
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
