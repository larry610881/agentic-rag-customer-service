"""SQL 訂單查詢服務 — 查詢 Olist 資料"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.agent.tool_services import OrderLookupService
from src.domain.agent.value_objects import ToolResult

_BASE_SELECT = """
    SELECT o.order_id, o.order_status, o.order_purchase_timestamp,
           o.order_estimated_delivery_date, p.product_category_name, i.price
    FROM olist_orders o
    LEFT JOIN olist_order_items i ON o.order_id = i.order_id
    LEFT JOIN olist_products p ON i.product_id = p.product_id
"""


class SQLOrderLookupService(OrderLookupService):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def lookup_order(
        self,
        *,
        order_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> ToolResult:
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if order_id:
            conditions.append("o.order_id = :order_id")
            params["order_id"] = order_id
        if status:
            conditions.append("o.order_status = :status")
            params["status"] = status

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        params["limit"] = limit

        query = text(
            f"{_BASE_SELECT}{where_clause}\n"
            "    ORDER BY o.order_purchase_timestamp DESC\n"
            "    LIMIT :limit"
        )

        async with self._session_factory() as session:
            result = await session.execute(query, params)
            rows = result.all()

        if not rows:
            if order_id:
                msg = f"找不到訂單 '{order_id}'"
            elif status:
                msg = f"沒有狀態為 '{status}' 的訂單"
            else:
                msg = "目前沒有任何訂單"
            return ToolResult(
                tool_name="order_lookup",
                success=False,
                error_message=msg,
            )

        def _row_to_dict(row: Any) -> dict[str, Any]:
            return {
                "order_id": row.order_id,
                "order_status": row.order_status,
                "purchase_timestamp": (
                    str(row.order_purchase_timestamp)
                    if row.order_purchase_timestamp
                    else None
                ),
                "estimated_delivery_date": (
                    str(row.order_estimated_delivery_date)
                    if row.order_estimated_delivery_date
                    else None
                ),
                "product_category": row.product_category_name,
                "price": float(row.price) if row.price else None,
            }

        # 單筆（by order_id）→ 回傳 data dict
        if order_id and len(rows) == 1:
            return ToolResult(
                tool_name="order_lookup",
                success=True,
                data=_row_to_dict(rows[0]),
            )

        # 多筆 → 回傳 {"orders": [...], "total": N}
        return ToolResult(
            tool_name="order_lookup",
            success=True,
            data={
                "orders": [_row_to_dict(r) for r in rows],
                "total": len(rows),
            },
        )
