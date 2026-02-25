"""訂單查詢用例"""

from dataclasses import dataclass

from src.domain.agent.tool_services import OrderLookupService
from src.domain.agent.value_objects import ToolResult


@dataclass(frozen=True)
class OrderLookupCommand:
    order_id: str | None = None
    status: str | None = None
    limit: int = 10


class OrderLookupUseCase:
    def __init__(self, order_lookup_service: OrderLookupService) -> None:
        self._service = order_lookup_service

    async def execute(self, command: OrderLookupCommand) -> ToolResult:
        return await self._service.lookup_order(
            order_id=command.order_id,
            status=command.status,
            limit=command.limit,
        )
