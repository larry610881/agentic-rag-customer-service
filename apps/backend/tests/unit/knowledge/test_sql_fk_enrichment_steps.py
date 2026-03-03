"""SQL FK Enrichment BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.text_splitter.sql_fk_enricher import ForeignKeyEnricher
from src.infrastructure.text_splitter.sql_schema_parser import (
    ColumnDef,
    ForeignKeyDef,
    TableSchema,
)

scenarios("unit/knowledge/sql_fk_enrichment.feature")


@pytest.fixture
def ctx():
    return {}


# --- Single FK enrichment ---


@given("一組含 orders 和 customers 表的 schema 與資料且 orders 有 FK 指向 customers")
def orders_customers_setup(ctx):
    customers_schema = TableSchema(
        name="customers",
        columns=[
            ColumnDef("id", "INT"),
            ColumnDef("name", "VARCHAR"),
            ColumnDef("email", "VARCHAR"),
        ],
        primary_key=["id"],
    )
    orders_schema = TableSchema(
        name="orders",
        columns=[
            ColumnDef("id", "INT"),
            ColumnDef("customer_id", "INT"),
            ColumnDef("total", "DECIMAL"),
        ],
        primary_key=["id"],
        foreign_keys=[
            ForeignKeyDef(
                source_table="orders",
                source_columns=("customer_id",),
                target_table="customers",
                target_columns=("id",),
            ),
        ],
    )
    ctx["schemas"] = [customers_schema, orders_schema]
    ctx["table_data"] = {
        "customers": [
            {"id": "1", "name": "Alice", "email": "alice@example.com"},
            {"id": "2", "name": "Bob", "email": "bob@example.com"},
        ],
        "orders": [
            {"id": "101", "customer_id": "1", "total": "99.99"},
        ],
    }
    ctx["table_name"] = "orders"


@when("執行 FK 豐富化")
def do_fk_enrichment(ctx):
    enricher = ForeignKeyEnricher(ctx["schemas"], ctx["table_data"])
    ctx["enricher"] = enricher
    rows = ctx["table_data"][ctx["table_name"]]
    ctx["enriched_rows"] = [
        enricher.enrich_row(ctx["table_name"], row) for row in rows
    ]


@then("orders 的每行應附加對應 customer 的描述欄位")
def verify_single_fk_enrichment(ctx):
    enriched = ctx["enriched_rows"][0]
    assert "[customers:" in enriched
    assert "name=Alice" in enriched
    assert "email=alice@example.com" in enriched


# --- FK target not found ---


@given("一組含 FK 但目標表資料中無對應 PK 值")
def fk_target_missing(ctx):
    customers_schema = TableSchema(
        name="customers",
        columns=[ColumnDef("id", "INT"), ColumnDef("name", "VARCHAR")],
        primary_key=["id"],
    )
    orders_schema = TableSchema(
        name="orders",
        columns=[ColumnDef("id", "INT"), ColumnDef("customer_id", "INT")],
        primary_key=["id"],
        foreign_keys=[
            ForeignKeyDef(
                source_table="orders",
                source_columns=("customer_id",),
                target_table="customers",
                target_columns=("id",),
            ),
        ],
    )
    ctx["schemas"] = [customers_schema, orders_schema]
    ctx["table_data"] = {
        "customers": [{"id": "1", "name": "Alice"}],
        "orders": [{"id": "101", "customer_id": "999"}],
    }
    ctx["table_name"] = "orders"


@then("該行不應附加任何關聯資料")
def verify_no_enrichment(ctx):
    enriched = ctx["enriched_rows"][0]
    assert "[" not in enriched


# --- Multiple FK enrichment ---


@given("一組含 order_items 表且有 FK 分別指向 orders 和 products")
def multi_fk_setup(ctx):
    orders_schema = TableSchema(
        name="orders",
        columns=[ColumnDef("id", "INT"), ColumnDef("status", "VARCHAR")],
        primary_key=["id"],
    )
    products_schema = TableSchema(
        name="products",
        columns=[ColumnDef("id", "INT"), ColumnDef("name", "VARCHAR")],
        primary_key=["id"],
    )
    order_items_schema = TableSchema(
        name="order_items",
        columns=[
            ColumnDef("id", "INT"),
            ColumnDef("order_id", "INT"),
            ColumnDef("product_id", "INT"),
            ColumnDef("qty", "INT"),
        ],
        primary_key=["id"],
        foreign_keys=[
            ForeignKeyDef(
                source_table="order_items",
                source_columns=("order_id",),
                target_table="orders",
                target_columns=("id",),
            ),
            ForeignKeyDef(
                source_table="order_items",
                source_columns=("product_id",),
                target_table="products",
                target_columns=("id",),
            ),
        ],
    )
    ctx["schemas"] = [orders_schema, products_schema, order_items_schema]
    ctx["table_data"] = {
        "orders": [{"id": "1", "status": "shipped"}],
        "products": [{"id": "10", "name": "Widget"}],
        "order_items": [{"id": "1", "order_id": "1", "product_id": "10", "qty": "3"}],
    }
    ctx["table_name"] = "order_items"


@then("order_items 的每行應同時附加 orders 和 products 的描述欄位")
def verify_multi_fk(ctx):
    enriched = ctx["enriched_rows"][0]
    assert "[orders:" in enriched
    assert "status=shipped" in enriched
    assert "[products:" in enriched
    assert "name=Widget" in enriched


# --- Noise field exclusion ---


@given("一組含 FK 且目標表有 _id 和 _at 結尾的欄位")
def fk_with_noise_fields(ctx):
    customers_schema = TableSchema(
        name="customers",
        columns=[
            ColumnDef("id", "INT"),
            ColumnDef("name", "VARCHAR"),
            ColumnDef("tenant_id", "INT"),
            ColumnDef("created_at", "TIMESTAMP"),
            ColumnDef("avatar_url", "VARCHAR"),
        ],
        primary_key=["id"],
    )
    orders_schema = TableSchema(
        name="orders",
        columns=[ColumnDef("id", "INT"), ColumnDef("customer_id", "INT")],
        primary_key=["id"],
        foreign_keys=[
            ForeignKeyDef(
                source_table="orders",
                source_columns=("customer_id",),
                target_table="customers",
                target_columns=("id",),
            ),
        ],
    )
    ctx["schemas"] = [customers_schema, orders_schema]
    ctx["table_data"] = {
        "customers": [
            {
                "id": "1",
                "name": "Alice",
                "tenant_id": "t1",
                "created_at": "2024-01-01",
                "avatar_url": "http://example.com/img.png",
            },
        ],
        "orders": [{"id": "101", "customer_id": "1"}],
    }
    ctx["table_name"] = "orders"


@then("附加的描述欄位應排除 _id 和 _at 結尾的噪音欄位")
def verify_noise_excluded(ctx):
    enriched = ctx["enriched_rows"][0]
    assert "name=Alice" in enriched
    assert "tenant_id" not in enriched
    assert "created_at" not in enriched
    assert "avatar_url" not in enriched
