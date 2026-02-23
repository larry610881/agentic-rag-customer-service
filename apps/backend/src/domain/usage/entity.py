"""Usage 限界上下文實體"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class UsageRecord:
    """LLM 使用記錄"""

    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    request_type: str = ""  # "rag" or "agent"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
