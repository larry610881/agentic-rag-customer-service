from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base

if TYPE_CHECKING:
    from src.infrastructure.db.models.bot_knowledge_base_model import BotKnowledgeBaseModel

TZDateTime = DateTime(timezone=True)


class BotModel(Base):
    __tablename__ = "bots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    short_code: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled_tools: Mapped[list] = mapped_column(
        JSON, nullable=False, default=lambda: ["rag_query"]
    )
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    show_sources: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    mcp_servers: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    mcp_bindings: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    max_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    audit_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="minimal", server_default="minimal"
    )
    eval_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    eval_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eval_depth: Mapped[str] = mapped_column(
        String(20), nullable=False, default="L1", server_default="L1"
    )
    base_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fab_icon_url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", server_default=""
    )
    widget_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    widget_allowed_origins: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    widget_keep_history: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    widget_welcome_message: Mapped[str] = mapped_column(
        String(500), nullable=False, default=""
    )
    widget_placeholder_text: Mapped[str] = mapped_column(
        String(200), nullable=False, default=""
    )
    widget_greeting_messages: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    widget_greeting_animation: Mapped[str] = mapped_column(
        String(20), nullable=False, default="fade"
    )
    memory_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    memory_extraction_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    memory_extraction_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    intent_routes: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    router_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    busy_reply_message: Mapped[str] = mapped_column(
        String(500), nullable=False,
        default="小編正在努力回覆中，請稍等一下喔～",
        server_default="小編正在努力回覆中，請稍等一下喔～",
    )
    line_channel_secret: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    line_channel_access_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    line_show_sources: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    history_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    frequency_penalty: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    reasoning_effort: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium"
    )
    rag_top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rag_score_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.3
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

    knowledge_bases: Mapped[list["BotKnowledgeBaseModel"]] = relationship(
        "BotKnowledgeBaseModel", lazy="raise"
    )

    __table_args__ = (
        Index("ix_bots_tenant_id", "tenant_id"),
    )
