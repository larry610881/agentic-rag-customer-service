"""商品搜尋用例"""

from src.domain.agent.tool_services import ProductSearchService
from src.domain.agent.value_objects import ToolResult


class ProductSearchUseCase:
    def __init__(self, product_search_service: ProductSearchService) -> None:
        self._service = product_search_service

    async def execute(self, keyword: str, limit: int = 5) -> ToolResult:
        return await self._service.search_products(keyword, limit)
