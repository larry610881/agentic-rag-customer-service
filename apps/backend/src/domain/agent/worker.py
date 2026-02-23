"""AgentWorker ABC — Multi-Agent 架構基礎"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.domain.conversation.entity import Message
from src.domain.rag.value_objects import Source, TokenUsage


@dataclass
class WorkerContext:
    tenant_id: str
    kb_id: str
    user_message: str
    conversation_history: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerResult:
    answer: str
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    usage: TokenUsage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentWorker(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def can_handle(self, context: WorkerContext) -> bool: ...

    @abstractmethod
    async def handle(self, context: WorkerContext) -> WorkerResult: ...
