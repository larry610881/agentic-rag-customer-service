"""SQL 商品搜尋服務 — 查詢 Olist 資料"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.agent.tool_services import ProductSearchService
from src.domain.agent.value_objects import ToolResult

PRODUCT_SEARCH_QUERY = text("""
    SELECT p.product_id, p.product_category_name,
           t.product_category_name_english, p.product_weight_g
    FROM olist_products p
    LEFT JOIN product_category_translation t
        ON p.product_category_name = t.product_category_name
    WHERE t.product_category_name_english ILIKE :keyword
       OR p.product_category_name ILIKE :keyword
    LIMIT :limit
""")


class SQLProductSearchService(ProductSearchService):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def search_products(
        self, keyword: str, limit: int = 5
    ) -> ToolResult:
        async with self._session_factory() as session:
            result = await session.execute(
                PRODUCT_SEARCH_QUERY,
                {"keyword": f"%{keyword}%", "limit": limit},
            )
            rows = result.fetchall()

        products = [
            {
                "product_id": row.product_id,
                "category": row.product_category_name,
                "category_english": row.product_category_name_english,
                "weight_g": row.product_weight_g,
            }
            for row in rows
        ]

        return ToolResult(
            tool_name="product_search",
            success=True,
            data={"products": products, "count": len(products)},
        )
