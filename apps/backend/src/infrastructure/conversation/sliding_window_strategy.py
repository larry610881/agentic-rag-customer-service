"""SlidingWindowStrategy — 只保留最近 N 條訊息"""

from src.domain.conversation.entity import Message
from src.domain.conversation.history_strategy import (
    ConversationHistoryStrategy,
    HistoryContext,
    HistoryStrategyConfig,
)

_DEFAULT_CONFIG = HistoryStrategyConfig()


def _format_messages(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        role_label = "用戶" if msg.role == "user" else "助手"
        lines.append(f"[{role_label}] {msg.content}")
    return "\n".join(lines)


class SlidingWindowStrategy(ConversationHistoryStrategy):
    @property
    def name(self) -> str:
        return "sliding_window"

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

        window = messages[-cfg.history_limit :]
        respond_context = _format_messages(window)
        router_msgs = window[-(cfg.router_context_limit * 2) :]
        router_context = _format_messages(router_msgs)

        return HistoryContext(
            respond_context=respond_context,
            router_context=router_context,
            message_count=len(window),
            strategy_name=self.name,
        )
