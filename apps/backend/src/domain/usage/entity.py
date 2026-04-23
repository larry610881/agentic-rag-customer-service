"""Usage 限界上下文實體"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class UsageRecord:
    """LLM 使用記錄 (Token-Gov.6: total_tokens 改為 @property，不再儲存冗餘欄位)"""

    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    request_type: str = ""  # See UsageCategory enum (src/domain/usage/category.py)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    message_id: str | None = None
    bot_id: str | None = None
    # KB 類任務歸屬 (OCR / Contextual Retrieval / Auto Classification / PDF Rename / Embedding)
    kb_id: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def total_tokens(self) -> int:
        """Token-Gov.6: total = input + output + cache_read + cache_creation (動態計算)

        以前是儲存欄位，與 4 個 raw 欄位重複；改為 property 後永不 drift。
        外部 read API（`.total_tokens`）維持不變。
        """
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )
