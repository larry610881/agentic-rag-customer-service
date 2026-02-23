"""Agent 限界上下文實體"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.domain.rag.value_objects import Source, TokenUsage


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    answer: str
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    conversation_id: str = ""
    usage: TokenUsage | None = None
    refund_step: str | None = None
    sentiment: str | None = None
    escalated: bool = False


@dataclass
class SupportTicket:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    subject: str = ""
    description: str = ""
    order_id: str = ""
    status: str = "open"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
