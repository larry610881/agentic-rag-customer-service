"""SQL 訂單查詢服務 — 查詢 Olist 資料"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.agent.tool_services import OrderLookupService
from src.domain.agent.value_objects import ToolResult

ORDER_QUERY = text("""
    SELECT o.order_id, o.order_status, o.order_purchase_timestamp,
           o.order_estimated_delivery_date, p.product_category_name, i.price
    FROM olist_orders o
    LEFT JOIN olist_order_items i ON o.order_id = i.order_id
    LEFT JOIN olist_products p ON i.product_id = p.product_id
    WHERE o.order_id = :order_id
    LIMIT 1
""")


class SQLOrderLookupService(OrderLookupService):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def lookup_order(self, order_id: str) -> ToolResult:
        async with self._session_factory() as session:
            result = await session.execute(
                ORDER_QUERY, {"order_id": order_id}
            )
            row = result.first()

        if row is None:
            return ToolResult(
                tool_name="order_lookup",
                success=False,
                error_message=f"Order '{order_id}' not found",
            )

        return ToolResult(
            tool_name="order_lookup",
            success=True,
            data={
                "order_id": row.order_id,
                "order_status": row.order_status,
                "purchase_timestamp": str(row.order_purchase_timestamp) if row.order_purchase_timestamp else None,
                "estimated_delivery_date": str(row.order_estimated_delivery_date) if row.order_estimated_delivery_date else None,
                "product_category": row.product_category_name,
                "price": float(row.price) if row.price else None,
            },
        )
