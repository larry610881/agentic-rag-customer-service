"""Feedback 分析值物件"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class DailyFeedbackStat:
    """每日回饋統計"""

    date: date
    total: int
    positive: int
    negative: int
    satisfaction_pct: float


@dataclass(frozen=True)
class TagCount:
    """標籤計數"""

    tag: str
    count: int


@dataclass(frozen=True)
class RetrievalQualityRecord:
    """檢索品質記錄（差評 + 上下文）"""

    user_question: str
    assistant_answer: str
    retrieved_chunks: list[dict[str, Any]]
    rating: str
    comment: str | None
    created_at: datetime
