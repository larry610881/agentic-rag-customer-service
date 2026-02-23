"""訂單查詢用例"""

from src.domain.agent.tool_services import OrderLookupService
from src.domain.agent.value_objects import ToolResult


class OrderLookupUseCase:
    def __init__(self, order_lookup_service: OrderLookupService) -> None:
        self._service = order_lookup_service

    async def execute(self, order_id: str) -> ToolResult:
        return await self._service.lookup_order(order_id)
