"""Agent 限界上下文值物件"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RefundStep(str, Enum):
    collect_order = "collect_order"
    collect_reason = "collect_reason"
    confirm = "confirm"


@dataclass(frozen=True)
class SentimentResult:
    sentiment: str  # "positive" | "neutral" | "negative"
    score: float
    should_escalate: bool = False


@dataclass(frozen=True)
class ToolName:
    value: str


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


@dataclass(frozen=True)
class AgentDecision:
    selected_tool: str
    reasoning: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
