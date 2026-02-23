"""Domain Events — 跨限界上下文異步通信基礎設施"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

EventHandler = Callable[["DomainEvent"], Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class DomainEvent:
    """所有 Domain Event 的基類"""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    tenant_id: str = ""


@dataclass(frozen=True)
class OrderRefunded(DomainEvent):
    order_id: str = ""
    amount: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class NegativeSentimentDetected(DomainEvent):
    conversation_id: str = ""
    sentiment_score: float = 0.0
    user_message: str = ""


@dataclass(frozen=True)
class CampaignCompleted(DomainEvent):
    campaign_id: str = ""
    reach: int = 0
    conversions: int = 0


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None: ...

    @abstractmethod
    async def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None: ...
