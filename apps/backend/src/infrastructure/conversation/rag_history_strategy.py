"""RAGHistoryStrategy — Stub 實作，暫時回退到 sliding_window 行為"""

from src.domain.conversation.entity import Message
from src.domain.conversation.history_strategy import (
    ConversationHistoryStrategy,
    HistoryContext,
    HistoryStrategyConfig,
)
from src.infrastructure.conversation.sliding_window_strategy import (
    SlidingWindowStrategy,
)


class RAGHistoryStrategy(ConversationHistoryStrategy):
    """Stub: 暫時委託 SlidingWindowStrategy，未來實作向量檢索歷史"""

    def __init__(self) -> None:
        self._fallback = SlidingWindowStrategy()

    @property
    def name(self) -> str:
        return "rag_history"

    async def process(
        self,
        messages: list[Message],
        config: HistoryStrategyConfig | None = None,
    ) -> HistoryContext:
        ctx = await self._fallback.process(messages, config)
        return HistoryContext(
            respond_context=ctx.respond_context,
            router_context=ctx.router_context,
            message_count=ctx.message_count,
            strategy_name=self.name,
        )
