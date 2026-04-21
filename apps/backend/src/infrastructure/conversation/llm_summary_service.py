"""LLM Conversation Summary Service — S-Gov.6b

實作 ConversationSummaryService ABC：用既有 LLMService 生中文一句話摘要，
再用既有 EmbeddingService 把摘要 embed 進 vector。

兩階段 token tracking 都透過 ConversationSummaryResult 5 個欄位回傳，
caller (GenerateConversationSummaryUseCase) 寫 RecordUsageUseCase 兩次。
"""

from __future__ import annotations

import logging

from src.domain.conversation.summary_service import (
    ConversationSummaryResult,
    ConversationSummaryService,
)
from src.domain.rag.services import EmbeddingService, LLMService

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """你是一個對話分析助手。
任務：針對使用者與 AI 客服機器人的對話，產生一句中文摘要（< 50 字），描述：
- 使用者的核心意圖（例如：詢問退貨流程、抱怨訂單延遲、查詢商品價格）
- 對話結果（例如：已解答、客戶滿意、需轉人工）

只輸出一句摘要，不要任何前後文、引號、編號、解釋。"""


def _build_user_message(messages: list[dict]) -> str:
    """把對話 messages 列表組成單一字串給 LLM。"""
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "").strip()
        if not content:
            continue
        prefix = "客戶" if role == "user" else "客服"
        lines.append(f"{prefix}：{content}")
    return "\n".join(lines)


class LLMConversationSummaryService(ConversationSummaryService):
    def __init__(
        self,
        llm_service: LLMService,
        embedding_service: EmbeddingService,
    ) -> None:
        self._llm = llm_service
        self._embedding = embedding_service

    async def summarize(
        self,
        *,
        messages: list[dict],
        lang_hint: str = "zh-TW",
    ) -> ConversationSummaryResult:
        # Step 1: LLM 生摘要
        user_message = _build_user_message(messages)
        if not user_message:
            raise ValueError("messages contain no content to summarize")

        llm_result = await self._llm.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            context="",  # 不需 RAG context
            temperature=0.3,
            max_tokens=120,
        )
        summary_text = llm_result.text.strip()
        if not summary_text:
            raise RuntimeError("LLM returned empty summary")

        # Step 2: embed summary
        embedding = await self._embedding.embed_query(summary_text)

        # Step 3: 從 embedding service 抓 token usage（既有 stateful 約定）
        embedding_tokens = int(
            getattr(self._embedding, "last_total_tokens", 0) or 0
        )
        embedding_model = str(
            getattr(self._embedding, "_model", "text-embedding-3-large")
        )

        return ConversationSummaryResult(
            summary=summary_text,
            embedding=embedding,
            summary_input_tokens=llm_result.usage.input_tokens,
            summary_output_tokens=llm_result.usage.output_tokens,
            summary_model=llm_result.usage.model,
            embedding_tokens=embedding_tokens,
            embedding_model=embedding_model,
        )
