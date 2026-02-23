"""Seed PostgreSQL with Olist data (CSV) or mock data fallback."""

import csv
import os
from pathlib import Path

import asyncpg


RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

CSV_TABLE_MAP = {
    "olist_customers_dataset.csv": "olist_customers",
    "olist_orders_dataset.csv": "olist_orders",
    "olist_products_dataset.csv": "olist_products",
    "olist_order_items_dataset.csv": "olist_order_items",
    "olist_order_reviews_dataset.csv": "olist_order_reviews",
    "product_category_name_translation.csv": "product_category_translation",
}


async def _create_schema(conn: asyncpg.Connection) -> None:
    sql = SCHEMA_FILE.read_text()
    await conn.execute(sql)
    print("Schema created.")


async def _load_csv(conn: asyncpg.Connection, csv_file: str, table: str) -> int:
    filepath = RAW_DIR / csv_file
    if not filepath.exists():
        return 0
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return 0
    columns = list(rows[0].keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
    col_names = ", ".join(columns)
    query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    count = 0
    for row in rows:
        values = [row[c] if row[c] != "" else None for c in columns]
        await conn.execute(query, *values)
        count += 1
    return count


async def _insert_mock_data(conn: asyncpg.Connection) -> None:
    """Insert minimal mock data for development."""
    print("No CSV files found. Inserting mock data...")

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


async def seed(database_url: str | None = None) -> None:
    """Main seed entry point."""
    dsn = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/agentic_rag",
    )
    conn = await asyncpg.connect(dsn)
    try:
        await _create_schema(conn)

        has_csv = any((RAW_DIR / f).exists() for f in CSV_TABLE_MAP)
        if has_csv:
            for csv_file, table in CSV_TABLE_MAP.items():
                count = await _load_csv(conn, csv_file, table)
                if count > 0:
                    print(f"  {table}: {count} rows loaded from {csv_file}")
        else:
            await _insert_mock_data(conn)

        result = await conn.fetchval("SELECT COUNT(*) FROM olist_customers")
        print(f"Seed complete. olist_customers count: {result}")
    finally:
        await conn.close()
