"""InMemoryEventBus — 記憶體內 Event Bus 實作（開發/測試用）"""

from collections import defaultdict

from src.domain.shared.events import DomainEvent, EventBus, EventHandler


class InMemoryEventBus(EventBus):
    """記憶體內 Event Bus：以 dict[event_type] → list[handler] 管理訂閱。

    適用於單行程開發與測試環境。
    生產環境應替換為 Redis Pub/Sub 實作。
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = (
            defaultdict(list)
        )

    async def publish(self, event: DomainEvent) -> None:
        event_type = type(event)
        for handler in self._handlers.get(event_type, []):
            await handler(event)

    async def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        self._handlers[event_type].append(handler)
