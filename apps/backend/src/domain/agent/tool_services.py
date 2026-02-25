"""Agent 工具服務介面"""

from abc import ABC, abstractmethod

from src.domain.agent.value_objects import ToolResult


class OrderLookupService(ABC):
    @abstractmethod
    async def lookup_order(
        self,
        *,
        order_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> ToolResult: ...


class ProductSearchService(ABC):
    @abstractmethod
    async def search_products(
        self, keyword: str, limit: int = 5
    ) -> ToolResult: ...


class TicketService(ABC):
    @abstractmethod
    async def create_ticket(
        self,
        tenant_id: str,
        subject: str,
        description: str,
        order_id: str = "",
    ) -> ToolResult: ...
