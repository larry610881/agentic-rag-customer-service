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
    # Assistant message 寫入 DB 後的 id，供 RecordUsage 建立 message↔usage 對應
    message_id: str | None = None
    usage: TokenUsage | None = None
    refund_step: str | None = None
    # 由 transfer_to_human_agent tool 產生的 channel-agnostic 聯絡按鈕
    # {"label": str, "url": str, "type": "url" | "phone"}
    contact: dict[str, Any] | None = None
    # Sprint A++ Guard UX: 該次回應是否由 prompt guard 攔截。
    #   None = 未攔截 / "input" = input rule 命中 / "output" = output keyword 命中
    # 只 Studio 端會暴露此 flag 供 UX 顯示；widget / LINE 路由會強制清成 None
    # 避免洩露防禦邏輯（見 agent_router.py 的 sanitize 邏輯）
    guard_blocked: str | None = None
    guard_rule_matched: str | None = None


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
