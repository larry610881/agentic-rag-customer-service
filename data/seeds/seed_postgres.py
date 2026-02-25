"""Seed PostgreSQL with Olist data (CSV) or mock data fallback.

Supports three modes:
  - "auto"  (default): use CSV if present, else mock
  - "mock":  force mock data only
  - "kaggle": force CSV, error if missing
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import asyncpg

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

# CSV filename → table name (insertion order respects FK dependencies)
CSV_TABLE_MAP = {
    "olist_customers_dataset.csv": "olist_customers",
    "olist_products_dataset.csv": "olist_products",
    "product_category_name_translation.csv": "product_category_translation",
    "olist_orders_dataset.csv": "olist_orders",
    "olist_order_items_dataset.csv": "olist_order_items",
    "olist_order_reviews_dataset.csv": "olist_order_reviews",
}

# Schema for type coercion: table → column → target type
TABLE_SCHEMA: dict[str, dict[str, type]] = {
    "olist_customers": {},  # all VARCHAR
    "olist_products": {
        "product_name_length": int,
        "product_description_length": int,
        "product_photos_qty": int,
        "product_weight_g": int,
        "product_length_cm": int,
        "product_height_cm": int,
        "product_width_cm": int,
    },
    "product_category_translation": {},  # all VARCHAR
    "olist_orders": {
        "order_purchase_timestamp": datetime,
        "order_approved_at": datetime,
        "order_delivered_carrier_date": datetime,
        "order_delivered_customer_date": datetime,
        "order_estimated_delivery_date": datetime,
    },
    "olist_order_items": {
        "order_item_id": int,
        "shipping_limit_date": datetime,
        "price": float,
        "freight_value": float,
    },
    "olist_order_reviews": {
        "review_score": int,
        "review_creation_date": datetime,
        "review_answer_timestamp": datetime,
    },
}

# Tables to truncate for Olist-only reset (reverse FK order)
OLIST_TABLES = [
    "support_tickets",
    "olist_order_reviews",
    "olist_order_items",
    "olist_orders",
    "olist_products",
    "olist_customers",
    "product_category_translation",
]

# Additional App tables for full reset (reverse FK order)
APP_TABLES = [
    "bot_knowledge_bases",
    "processing_tasks",
    "chunks",
    "documents",
    "knowledge_bases",
    "bots",
    "messages",
    "conversations",
    "token_usage_records",
    "tenants",
]


def _coerce(value: str, target_type: type) -> Any:
    """Convert CSV string to Python type."""
    if value == "":
        return None
    if target_type is datetime:
        return datetime.fromisoformat(value)
    if target_type is int:
        return int(float(value))
    if target_type is float:
        return float(value)
    return value


async def _create_schema(conn: asyncpg.Connection) -> None:
    sql = SCHEMA_FILE.read_text()
    await conn.execute(sql)
    print("Schema created.")


async def _table_count(conn: asyncpg.Connection, table: str) -> int:
    return await conn.fetchval(f"SELECT COUNT(*) FROM {table}")  # noqa: S608


async def _load_csv_fast(conn: asyncpg.Connection, csv_file: str, table: str) -> int:
    """Load CSV into table using asyncpg copy_records_to_table (COPY protocol)."""
    filepath = RAW_DIR / csv_file
    if not filepath.exists():
        return 0

    # Skip if table already has data
    existing = await _table_count(conn, table)
    if existing > 0:
        print(f"  {table}: already has {existing} rows, skipping.")
        return 0

    schema = TABLE_SCHEMA.get(table, {})

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        if not columns:
            return 0

        records: list[tuple[Any, ...]] = []
        for row in reader:
            values = tuple(
                _coerce(row[col], schema.get(col, str)) for col in columns
            )
            records.append(values)

    if not records:
        return 0

    await conn.copy_records_to_table(
        table,
        records=records,
        columns=columns,
    )
    return len(records)


async def _insert_mock_data(conn: asyncpg.Connection) -> None:
    """Insert minimal mock data for development."""
    print("Inserting mock data...")

    await conn.execute("""
        INSERT INTO olist_customers (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
        VALUES
            ('cust-001', 'u-001', '01310', 'sao paulo', 'SP'),
            ('cust-002', 'u-002', '20040', 'rio de janeiro', 'RJ'),
            ('cust-003', 'u-003', '30130', 'belo horizonte', 'MG')
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO olist_orders (order_id, customer_id, order_status, order_purchase_timestamp)
        VALUES
            ('ord-001', 'cust-001', 'delivered', '2024-01-15 10:00:00'),
            ('ord-002', 'cust-002', 'shipped', '2024-02-20 14:30:00'),
            ('ord-003', 'cust-003', 'processing', '2024-03-10 09:15:00')
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO olist_products (product_id, product_category_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm)
        VALUES
            ('prod-001', 'informatica_acessorios', 300, 20, 5, 15),
            ('prod-002', 'telefonia', 200, 15, 8, 8),
            ('prod-003', 'eletronicos', 1500, 40, 30, 25)
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO olist_order_items (order_id, order_item_id, product_id, seller_id, price, freight_value)
        VALUES
            ('ord-001', 1, 'prod-001', 'seller-001', 99.90, 15.50),
            ('ord-002', 1, 'prod-002', 'seller-002', 249.00, 20.00),
            ('ord-003', 1, 'prod-003', 'seller-001', 1299.00, 45.00)
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO product_category_translation (product_category_name, product_category_name_english)
        VALUES
            ('informatica_acessorios', 'computers_accessories'),
            ('telefonia', 'telephony'),
            ('eletronicos', 'electronics')
        ON CONFLICT DO NOTHING
    """)

    print("Mock data inserted: 3 customers, 3 orders, 3 products, 3 order items.")


async def _insert_demo_orders(conn: asyncpg.Connection) -> None:
    """Ensure demo orders (ord-001~003) exist for E2E tests.

    Uses cust-demo-xxx prefix to avoid collision with Kaggle UUIDs.
    Called in both mock and kaggle modes.
    """
    await conn.execute("""
        INSERT INTO olist_customers (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
        VALUES
            ('cust-demo-001', 'u-demo-001', '01310', 'sao paulo', 'SP'),
            ('cust-demo-002', 'u-demo-002', '20040', 'rio de janeiro', 'RJ'),
            ('cust-demo-003', 'u-demo-003', '30130', 'belo horizonte', 'MG')
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO olist_orders (order_id, customer_id, order_status, order_purchase_timestamp)
        VALUES
            ('ord-001', 'cust-demo-001', 'delivered', '2024-01-15 10:00:00'),
            ('ord-002', 'cust-demo-002', 'shipped', '2024-02-20 14:30:00'),
            ('ord-003', 'cust-demo-003', 'processing', '2024-03-10 09:15:00')
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO olist_products (product_id, product_category_name, product_weight_g, product_length_cm, product_height_cm, product_width_cm)
        VALUES
            ('prod-demo-001', 'informatica_acessorios', 300, 20, 5, 15),
            ('prod-demo-002', 'telefonia', 200, 15, 8, 8),
            ('prod-demo-003', 'eletronicos', 1500, 40, 30, 25)
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO olist_order_items (order_id, order_item_id, product_id, seller_id, price, freight_value)
        VALUES
            ('ord-001', 1, 'prod-demo-001', 'seller-demo-001', 99.90, 15.50),
            ('ord-002', 1, 'prod-demo-002', 'seller-demo-002', 249.00, 20.00),
            ('ord-003', 1, 'prod-demo-003', 'seller-demo-001', 1299.00, 45.00)
        ON CONFLICT DO NOTHING
    """)

    await conn.execute("""
        INSERT INTO product_category_translation (product_category_name, product_category_name_english)
        VALUES
            ('informatica_acessorios', 'computers_accessories'),
            ('telefonia', 'telephony'),
            ('eletronicos', 'electronics')
        ON CONFLICT DO NOTHING
    """)


async def reset_olist(conn: asyncpg.Connection) -> None:
    """Truncate Olist tables only (preserve App data)."""
    for table in OLIST_TABLES:
        await conn.execute(f"TRUNCATE TABLE {table} CASCADE")  # noqa: S608
    print(f"Reset complete: {len(OLIST_TABLES)} Olist tables truncated.")


async def reset_all(conn: asyncpg.Connection) -> None:
    """Truncate all tables (Olist + App)."""
    all_tables = OLIST_TABLES + APP_TABLES
    for table in all_tables:
        try:
            await conn.execute(f"TRUNCATE TABLE {table} CASCADE")  # noqa: S608
        except asyncpg.UndefinedTableError:
            print(f"  {table}: table does not exist, skipping.")
    print(f"Full reset complete: {len(all_tables)} tables truncated.")


async def status(conn: asyncpg.Connection) -> dict[str, int]:
    """Return row count for each known table."""
    counts: dict[str, int] = {}
    all_tables = OLIST_TABLES + APP_TABLES
    for table in all_tables:
        try:
            counts[table] = await _table_count(conn, table)
        except asyncpg.UndefinedTableError:
            counts[table] = -1  # table doesn't exist
    return counts


def _detect_mode(counts: dict[str, int]) -> str:
    """Detect current data mode from row counts."""
    customers = counts.get("olist_customers", 0)
    if customers > 100:
        return "kaggle"
    elif customers > 0:
        return "mock"
    return "empty"


async def seed(
    database_url: str | None = None,
    mode: Literal["auto", "mock", "kaggle"] = "auto",
) -> None:
    """Main seed entry point.

    Args:
        database_url: PostgreSQL connection string (falls back to DATABASE_URL env).
        mode: "auto" (CSV if present, else mock), "mock", or "kaggle".
    """
    dsn = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/agentic_rag",
    )
    conn = await asyncpg.connect(dsn)
    try:
        await _create_schema(conn)

        has_csv = all((RAW_DIR / f).exists() for f in CSV_TABLE_MAP)

        if mode == "kaggle":
            if not has_csv:
                print("ERROR: mode='kaggle' but CSV files not found in data/raw/.")
                print("Run 'make seed-kaggle' or download manually first.")
                return
            print("Loading Kaggle CSV data (COPY protocol)...")
            for csv_file, table in CSV_TABLE_MAP.items():
                count = await _load_csv_fast(conn, csv_file, table)
                if count > 0:
                    print(f"  {table}: {count} rows loaded from {csv_file}")
            await _insert_demo_orders(conn)

        elif mode == "mock":
            await _insert_mock_data(conn)

        else:  # auto
            if has_csv:
                print("CSV files detected — loading Kaggle data (COPY protocol)...")
                for csv_file, table in CSV_TABLE_MAP.items():
                    count = await _load_csv_fast(conn, csv_file, table)
                    if count > 0:
                        print(f"  {table}: {count} rows loaded from {csv_file}")
                await _insert_demo_orders(conn)
            else:
                print("No CSV files found. Falling back to mock data.")
                await _insert_mock_data(conn)

        result = await conn.fetchval("SELECT COUNT(*) FROM olist_customers")
        print(f"Seed complete. olist_customers count: {result}")
    finally:
        await conn.close()
