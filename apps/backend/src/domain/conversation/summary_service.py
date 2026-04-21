"""Conversation Summary Service ABC — S-Gov.6b

Domain port：產生「對話摘要 + 同段話的 embedding」，回傳結果含
完整 token tracking 資訊（給 caller 寫 RecordUsageUseCase 用）。

設計選擇：result-based 而非 stateful（與 LLMChunkContextService 不同）：
- SummaryService 同時做 LLM + embedding 兩件事，stateful 兩組 attribute 易混淆
- result-based 純函數風格，unit test 易寫
- caller 從 result 取兩組 token，各自呼叫 record_usage（一次 LLM、一次 EMBEDDING）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationSummaryResult:
    """LLM 摘要 + embedding 結果，含完整 token tracking 資訊。"""

    summary: str  # 中文一句話摘要
    embedding: list[float]  # 3072 dim from text-embedding-3-large

    # Token tracking — caller 走 record_usage 用
    summary_input_tokens: int
    summary_output_tokens: int
    summary_model: str

    embedding_tokens: int
    embedding_model: str


class ConversationSummaryService(ABC):
    @abstractmethod
    async def summarize(
        self,
        *,
        messages: list[dict],
        lang_hint: str = "zh-TW",
    ) -> ConversationSummaryResult:
        """生成對話摘要 + embedding。

        Args:
            messages: list of {"role": "user"|"assistant", "content": str}
            lang_hint: 摘要語言（預設繁中）

        Returns:
            ConversationSummaryResult with full token tracking fields.

        Raises:
            Exception: 任何階段失敗 raise；caller 決定 retry 策略。
        """
        ...
