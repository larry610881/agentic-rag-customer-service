"""JoyInKitchen MCP Server — 窩廚房業務資料查詢工具

提供課程查詢、商品查詢等 Tools，供 AI 客服 Agent 透過 MCP 協議呼叫。
使用 PostgreSQL (asyncpg) 作為資料來源。
"""

import json
import os
import re
from datetime import datetime, timezone

import asyncpg
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "joyinkitchen",
    host="0.0.0.0",
    port=int(os.getenv("MCP_PORT", "9000")),
    instructions="""你是窩廚房（JoyInKitchen）的業務資料查詢助手。
你可以查詢：
1. 商品資訊（名稱、價格、分類、運送方式）
2. 課程資訊（名稱、時間、價格、講師、剩餘名額）
使用規則：
- 客戶用具體條件篩選商品（價格、分類、運送方式、商品名稱）→ search_products
- 客戶用具體條件查課程（日期、講師、名額、課程名稱）→ search_courses
- 每個工具最多呼叫一次，不要用不同參數重複查詢
- 回傳結果為 JSON，請用自然語言整理後回覆客戶
""",
)

# ---------------------------------------------------------------------------
# DB Connection Pool
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        db_url = os.getenv("DATABASE_URL_OVERRIDE")
        if db_url:
            # 移除 SQLAlchemy driver prefix（如 postgresql+asyncpg://）
            clean_url = re.sub(r"^postgresql\+\w+://", "postgresql://", db_url)
            _pool = await asyncpg.create_pool(dsn=clean_url, min_size=1, max_size=5)
        else:
            # fallback 個別 env vars（本地開發）
            _pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                port=int(os.getenv("DB_PORT", "5432")),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "postgres"),
                database=os.getenv("DB_NAME", "agentic_rag"),
                min_size=1,
                max_size=5,
            )
    return _pool


def _ts_to_str(ts: int | None) -> str | None:
    """Unix timestamp → 人類可讀的台灣時間字串"""
    if not ts:
        return None
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M")


SHIP_TYPE_MAP = {1: "常溫", 2: "低溫", 3: "冷凍"}


# ---------------------------------------------------------------------------
# Tool 1: 搜尋商品
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_products(
    keyword: str = "",
    product_id: int | None = None,
    category: str = "",
    min_price: int | None = None,
    max_price: int | None = None,
    ship_type: int | None = None,
    limit: int = 5,
) -> str:
    """用具體條件篩選窩廚房上架中的商品。回傳商品名稱、售價、分類、運送方式。

    注意：此工具用於「具體條件篩選」，不適用於「推薦」「適合」等開放性問題。
    推薦型問題請使用 rag_query 查知識庫。

    適用情境：
    - 客戶問「有沒有冷凍宅配的食品？」→ ship_type=3
    - 客戶問「XX 商品多少錢？」→ keyword="XX"
    - 客戶問「500 元以下的商品」→ max_price=500
    - 客戶指定商品 ID → product_id=123

    Args:
        keyword: 商品名稱或說明的模糊搜尋，留空回傳熱門商品
        product_id: 精確查詢特定商品 ID
        category: 分類名稱篩選（模糊比對）
        min_price: 最低價格篩選
        max_price: 最高價格篩選
        ship_type: 運送方式（1=常溫, 2=低溫, 3=冷凍）
        limit: 回傳筆數上限（預設 5，最大 20）
    """
    limit = min(max(limit, 1), 20)
    pool = await _get_pool()

    conditions = ["p.is_online = 1", "p.status = 1"]
    params: list = []
    param_idx = 0
    need_category_join = bool(category)

    if product_id is not None:
        param_idx += 1
        conditions.append(f"p.id = ${param_idx}")
        params.append(product_id)

    if keyword:
        param_idx += 1
        kw_param = f"${param_idx}"
        conditions.append(
            f"(p.name ILIKE {kw_param} OR p.description ILIKE {kw_param})"
        )
        params.append(f"%{keyword}%")

    if min_price is not None:
        param_idx += 1
        conditions.append(f"p.price >= ${param_idx}")
        params.append(min_price)

    if max_price is not None:
        param_idx += 1
        conditions.append(f"p.price <= ${param_idx}")
        params.append(max_price)

    if ship_type is not None:
        param_idx += 1
        conditions.append(f"p.ship_type = ${param_idx}")
        params.append(ship_type)

    if category:
        param_idx += 1
        conditions.append(f"pc.name ILIKE ${param_idx}")
        params.append(f"%{category}%")

    category_join = ""
    category_select = "NULL AS category_name"
    if need_category_join:
        category_join = """
            INNER JOIN product_product_category ppc ON ppc.product_id = p.id
            INNER JOIN product_categories pc ON pc.id = ppc.product_category_id
        """
        category_select = "pc.name AS category_name"
    else:
        category_join = """
            LEFT JOIN product_product_category ppc ON ppc.product_id = p.id
            LEFT JOIN product_categories pc ON pc.id = ppc.product_category_id
        """
        category_select = "pc.name AS category_name"

    where_clause = " AND ".join(conditions)

    # Order by keyword relevance or popularity
    if keyword:
        param_idx += 1
        order_clause = f"(p.name ILIKE ${param_idx}) DESC, p.buy_count DESC"
        params.append(f"%{keyword}%")
    else:
        order_clause = "p.buy_count DESC"

    param_idx += 1
    params.append(limit)

    query = f"""
        SELECT DISTINCT ON (p.id)
            p.id,
            p.name AS product_name,
            p.price,
            p.list_price,
            p.description,
            p.ship_type,
            p.buy_count,
            {category_select}
        FROM products p
        {category_join}
        WHERE {where_clause}
        ORDER BY p.id, {order_clause}
        LIMIT ${param_idx}
    """

    # asyncpg doesn't support DISTINCT ON + ORDER BY in the same way easily,
    # so use a subquery approach instead
    query = f"""
        SELECT * FROM (
            SELECT DISTINCT ON (p.id)
                p.id,
                p.name AS product_name,
                p.price,
                p.list_price,
                p.description,
                p.ship_type,
                p.buy_count,
                {category_select}
            FROM products p
            {category_join}
            WHERE {where_clause}
        ) sub
        ORDER BY {"(sub.product_name ILIKE $" + str(param_idx - 1) + ") DESC, " if keyword else ""}sub.buy_count DESC
        LIMIT ${param_idx}
    """

    # Simplify: skip DISTINCT ON, just use GROUP BY or simple query
    # Since product_categories is many-to-many, use a simpler approach
    query = f"""
        SELECT
            p.id,
            p.name AS product_name,
            p.price,
            p.list_price,
            p.description,
            p.ship_type,
            p.buy_count,
            (SELECT string_agg(pc2.name, ', ')
             FROM product_product_category ppc2
             JOIN product_categories pc2 ON pc2.id = ppc2.product_category_id
             WHERE ppc2.product_id = p.id) AS category_name
        FROM products p
        {"INNER JOIN product_product_category ppc ON ppc.product_id = p.id INNER JOIN product_categories pc ON pc.id = ppc.product_category_id" if need_category_join else ""}
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT ${param_idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    if not rows:
        return json.dumps(
            {"success": True, "message": "目前沒有符合條件的商品", "products": []},
            ensure_ascii=False,
        )

    products = []
    for row in rows:
        products.append(
            {
                "product_id": row["id"],
                "name": row["product_name"],
                "category": row["category_name"],
                "price": row["price"],
                "list_price": row["list_price"],
                "ship_type": SHIP_TYPE_MAP.get(row["ship_type"], "未知"),
                "description": row["description"],
                "buy_count": row["buy_count"],
            }
        )

    return json.dumps(
        {"success": True, "products": products, "total": len(products)},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Tool 2: 查詢課程
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_courses(
    keyword: str = "",
    course_id: int | None = None,
    category: str = "",
    lector: str = "",
    date_from: str = "",
    date_to: str = "",
    min_price: int | None = None,
    max_price: int | None = None,
    has_vacancy: bool = True,
    limit: int = 5,
) -> str:
    """查詢窩廚房的料理課程，回傳課程名稱、開課時間、售價、剩餘名額、講師。

    適用情境：
    - 客戶問「最近有什麼課？」→ keyword="" + has_vacancy=True
    - 客戶問「有沒有做麵包的課？」→ keyword="麵包"
    - 客戶問「XX 老師的課程」→ lector="XX"
    - 客戶問「下個月有什麼課？」→ date_from="2026-04-01", date_to="2026-04-30"
    - 客戶問「XX 課還有名額嗎？」→ keyword="XX" + has_vacancy=True
    - 客戶問「3000 元以下的課程」→ max_price=3000

    Args:
        keyword: 課程名稱模糊搜尋
        course_id: 精確查詢特定課程 ID
        category: 課程分類名稱篩選（模糊比對）
        lector: 講師姓名篩選（模糊比對）
        date_from: 開課日期起始（格式 YYYY-MM-DD）
        date_to: 開課日期結束（格式 YYYY-MM-DD）
        min_price: 最低價格篩選
        max_price: 最高價格篩選
        has_vacancy: 是否只顯示有剩餘名額的課程（預設 True）
        limit: 回傳筆數上限（預設 5，最大 20）
    """
    limit = min(max(limit, 1), 20)
    pool = await _get_pool()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    conditions = ["c.is_online = 1", "c.status = 1"]
    params: list = []
    param_idx = 0

    # Only show future courses by default
    param_idx += 1
    conditions.append(f"cs.start_at > ${param_idx}")
    params.append(now_ts)

    if course_id is not None:
        param_idx += 1
        conditions.append(f"c.id = ${param_idx}")
        params.append(course_id)

    if keyword:
        param_idx += 1
        conditions.append(f"c.name ILIKE ${param_idx}")
        params.append(f"%{keyword}%")

    if category:
        param_idx += 1
        conditions.append(f"cc.name ILIKE ${param_idx}")
        params.append(f"%{category}%")

    if lector:
        param_idx += 1
        conditions.append(f"l.name ILIKE ${param_idx}")
        params.append(f"%{lector}%")

    if date_from:
        try:
            from_ts = int(
                datetime.strptime(date_from, "%Y-%m-%d")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            param_idx += 1
            conditions.append(f"cs.start_at >= ${param_idx}")
            params.append(from_ts)
        except ValueError:
            pass

    if date_to:
        try:
            to_ts = int(
                datetime.strptime(date_to, "%Y-%m-%d")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            # End of day
            to_ts += 86400
            param_idx += 1
            conditions.append(f"cs.start_at < ${param_idx}")
            params.append(to_ts)
        except ValueError:
            pass

    if min_price is not None:
        param_idx += 1
        conditions.append(f"c.price >= ${param_idx}")
        params.append(min_price)

    if max_price is not None:
        param_idx += 1
        conditions.append(f"c.price <= ${param_idx}")
        params.append(max_price)

    where_clause = " AND ".join(conditions)
    having_clause = ""
    if has_vacancy:
        having_clause = "HAVING (cs.open_number - COALESCE(SUM(csr.buy_number), 0)) > 0"

    param_idx += 1
    params.append(limit)

    query = f"""
        SELECT
            c.id,
            c.name           AS course_name,
            c.price,
            c.list_price,
            c.description,
            cc.name          AS category_name,
            cs.start_at,
            cs.end_at,
            cs.deadline_at,
            cs.open_number,
            cs.open_number - COALESCE(SUM(csr.buy_number), 0) AS remaining_seats,
            l.name           AS lector_name
        FROM courses c
        INNER JOIN course_stocks cs ON cs.course_id = c.id
        LEFT JOIN course_stock_records csr ON csr.course_stock_id = cs.id
        LEFT JOIN course_categories cc ON cc.id = c.course_category_id
        LEFT JOIN course_lector cl ON cl.course_id = c.id
        LEFT JOIN lectors l ON l.id = cl.lector_id
        WHERE {where_clause}
        GROUP BY c.id, cs.id, cc.name, l.name
        {having_clause}
        ORDER BY cs.start_at ASC
        LIMIT ${param_idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    if not rows:
        return json.dumps(
            {"success": True, "message": "目前沒有符合條件的課程", "courses": []},
            ensure_ascii=False,
        )

    courses = []
    for row in rows:
        courses.append(
            {
                "course_id": row["id"],
                "name": row["course_name"],
                "category": row["category_name"],
                "lector": row["lector_name"],
                "price": row["price"],
                "list_price": row["list_price"],
                "start_at": _ts_to_str(row["start_at"]),
                "end_at": _ts_to_str(row["end_at"]),
                "deadline": _ts_to_str(row["deadline_at"]),
                "remaining_seats": int(row["remaining_seats"]),
                "description": row["description"],
            }
        )

    return json.dumps(
        {"success": True, "courses": courses, "total": len(courses)},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
