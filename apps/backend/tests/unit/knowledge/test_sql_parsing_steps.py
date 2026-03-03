"""SQL Schema Parsing BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.text_splitter.sql_schema_parser import (
    SqlDialect,
    SqlSchemaParser,
)

scenarios("unit/knowledge/sql_parsing.feature")


@pytest.fixture
def ctx():
    return {}


# --- Dialect detection ---


@given("一段包含 backtick 和 ENGINE= 的 SQL dump")
def mysql_dump(ctx):
    ctx["text"] = """
CREATE TABLE `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `users` (`id`, `name`) VALUES (1, 'Alice');
"""


@given("一段包含 COPY FROM stdin 和 serial 的 SQL dump")
def pg_dump(ctx):
    ctx["text"] = """
CREATE TABLE users (
  id serial NOT NULL,
  name VARCHAR(100),
  PRIMARY KEY (id)
);

COPY users (id, name) FROM stdin;
1\tAlice
\\.
"""


@when("執行方言偵測")
def detect_dialect(ctx):
    ctx["dialect"] = SqlSchemaParser.detect_dialect(ctx["text"])


@then("結果應為 mysql")
def verify_mysql(ctx):
    assert ctx["dialect"] == SqlDialect.MYSQL


@then("結果應為 postgresql")
def verify_pg(ctx):
    assert ctx["dialect"] == SqlDialect.POSTGRESQL


# --- DDL parsing ---


@given("一段 MySQL CREATE TABLE 語句")
def mysql_create_table(ctx):
    ctx["text"] = """
CREATE TABLE `products` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255),
  `price` DECIMAL(10,2),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
"""
    ctx["dialect"] = SqlDialect.MYSQL
    ctx["expected_table"] = "products"
    ctx["expected_columns"] = ["id", "name", "price"]


@given("一段 PostgreSQL CREATE TABLE 語句")
def pg_create_table(ctx):
    ctx["text"] = """
CREATE TABLE products (
  id serial NOT NULL,
  name VARCHAR(255),
  price DECIMAL(10,2),
  PRIMARY KEY (id)
);
"""
    ctx["dialect"] = SqlDialect.POSTGRESQL
    ctx["expected_table"] = "products"
    ctx["expected_columns"] = ["id", "name", "price"]


@when("執行 DDL 解析")
def parse_ddl(ctx):
    ctx["schemas"] = SqlSchemaParser.parse_tables(ctx["text"], ctx["dialect"])


@then("應解析出正確的表名與欄位清單")
def verify_table_and_columns(ctx):
    schemas = ctx["schemas"]
    assert len(schemas) >= 1
    schema = schemas[0]
    assert schema.name == ctx["expected_table"]
    col_names = [c.name for c in schema.columns]
    for expected in ctx["expected_columns"]:
        assert expected in col_names


# --- FK parsing ---


@given("一段包含 FOREIGN KEY 約束的 CREATE TABLE 語句")
def create_with_fk(ctx):
    ctx["text"] = """
CREATE TABLE customers (
  id INT NOT NULL,
  name VARCHAR(100),
  PRIMARY KEY (id)
);

CREATE TABLE orders (
  id INT NOT NULL,
  customer_id INT NOT NULL,
  total DECIMAL(10,2),
  PRIMARY KEY (id),
  FOREIGN KEY (customer_id) REFERENCES customers (id)
);
"""
    ctx["dialect"] = SqlDialect.MYSQL


@then("應解析出正確的外鍵關聯")
def verify_fk(ctx):
    schemas = ctx["schemas"]
    orders_schema = next(s for s in schemas if s.name == "orders")
    assert len(orders_schema.foreign_keys) == 1
    fk = orders_schema.foreign_keys[0]
    assert fk.source_table == "orders"
    assert fk.source_columns == ("customer_id",)
    assert fk.target_table == "customers"
    assert fk.target_columns == ("id",)
