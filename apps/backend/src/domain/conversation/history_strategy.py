"""對話歷史策略介面 — Strategy Pattern"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.conversation.entity import Message


@dataclass(frozen=True)
class HistoryContext:
    """策略處理後的歷史上下文"""

    respond_context: str  # 完整上下文（給 respond_node）
    router_context: str  # 精簡上下文（給 router_node 意圖分類）
    message_count: int
    strategy_name: str


@dataclass(frozen=True)
class HistoryStrategyConfig:
    """策略配置"""

    history_limit: int = 10
    recent_turns: int = 3
    summary_max_tokens: int = 200
    router_context_limit: int = 3


class ConversationHistoryStrategy(ABC):
    """對話歷史處理策略介面"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def process(
        self,
        messages: list[Message],
        config: HistoryStrategyConfig | None = None,
    ) -> HistoryContext: ...
