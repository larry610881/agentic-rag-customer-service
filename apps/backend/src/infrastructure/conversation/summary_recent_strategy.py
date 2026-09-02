"""SummaryRecentStrategy — 舊對話壓縮成摘要 + 最近 N 輪完整保留"""

from typing import Any

import structlog

from src.domain.conversation.entity import Message
from src.domain.conversation.history_strategy import (
    ConversationHistoryStrategy,
    HistoryContext,
    HistoryStrategyConfig,
)
from src.domain.rag.services import LLMService
from src.domain.shared.cache_service import CacheService

logger = structlog.get_logger(__name__)

_DEFAULT_CONFIG = HistoryStrategyConfig()

_SUMMARY_SYSTEM_PROMPT = (
    "你是一個對話摘要助手。請將以下對話歷史壓縮成簡潔的摘要，"
    "保留關鍵資訊（訂單號、商品名、用戶偏好、問題要點）。"
    "用繁體中文回覆，不超過 200 字。"
)


def _format_messages(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        role_label = "用戶" if msg.role == "user" else "助手"
        lines.append(f"[{role_label}] {msg.content}")
    return "\n".join(lines)


class SummaryRecentStrategy(ConversationHistoryStrategy):
    def __init__(
        self,
        llm_service: LLMService,
        cache_service: CacheService | None = None,
        cache_ttl: int = 3600,
        record_usage: Any | None = None,
    ) -> None:
        self._llm_service = llm_service
        self._cache_service = cache_service
        self._cache_ttl = cache_ttl
        # Issue #59：摘要 LLM 呼叫原本沒記帳
        self._record_usage = record_usage

    @property
    def name(self) -> str:
        return "summary_recent"

    async def process(
        self,
        messages: list[Message],
        config: HistoryStrategyConfig | None = None,
    ) -> HistoryContext:
        cfg = config or _DEFAULT_CONFIG
        if not messages:
            return HistoryContext(
                respond_context="",
                router_context="",
                message_count=0,
                strategy_name=self.name,
            )

        recent_count = cfg.recent_turns * 2
        if len(messages) <= recent_count:
            formatted = _format_messages(messages)
            return HistoryContext(
                respond_context=formatted,
                router_context=formatted,
                message_count=len(messages),
                strategy_name=self.name,
            )

        old_messages = messages[:-recent_count]
        recent_messages = messages[-recent_count:]

        summary = await self._summarize(old_messages, tenant_id=cfg.tenant_id)
        recent_text = _format_messages(recent_messages)

        respond_context = f"[對話摘要] {summary}\n\n{recent_text}"
        router_context = f"[對話摘要] {summary}"

        return HistoryContext(
            respond_context=respond_context,
            router_context=router_context,
            message_count=len(messages),
            strategy_name=self.name,
        )

    async def _summarize(
        self, messages: list[Message], tenant_id: str = ""
    ) -> str:
        cache_key = f"conv_summary:{len(messages)}:{messages[-1].id.value}"

        if self._cache_service is not None:
            cached = await self._cache_service.get(cache_key)
            if cached is not None:
                return cached

        conversation_text = _format_messages(messages)
        result = await self._llm_service.generate(
            _SUMMARY_SYSTEM_PROMPT,
            "請摘要以下對話：",
            conversation_text,
            max_tokens=200,
        )

        if self._record_usage is not None and tenant_id:
            from src.domain.usage.category import UsageCategory

            try:
                await self._record_usage.execute(
                    tenant_id=tenant_id,
                    request_type=UsageCategory.HISTORY_SUMMARY.value,
                    usage=result.usage,
                )
            except Exception:
                logger.warning("history_summary.usage_record_failed", exc_info=True)

        if self._cache_service is not None:
            await self._cache_service.set(
                cache_key, result.text, ttl_seconds=self._cache_ttl
            )
        return result.text
