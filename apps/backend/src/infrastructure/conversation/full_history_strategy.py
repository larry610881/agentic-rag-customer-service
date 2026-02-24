"""FullHistoryStrategy — 傳全部歷史，不壓縮"""

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


class FullHistoryStrategy(ConversationHistoryStrategy):
    @property
    def name(self) -> str:
        return "full"

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

        respond_context = _format_messages(messages)
        router_msgs = messages[-(cfg.router_context_limit * 2) :]
        router_context = _format_messages(router_msgs)

        return HistoryContext(
            respond_context=respond_context,
            router_context=router_context,
            message_count=len(messages),
            strategy_name=self.name,
        )
