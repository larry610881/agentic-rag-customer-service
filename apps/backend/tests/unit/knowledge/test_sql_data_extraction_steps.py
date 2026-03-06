"""SQL Data Extraction BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.text_splitter.sql_data_extractor import SqlDataExtractor
from src.infrastructure.text_splitter.sql_schema_parser import (
    SqlDialect,
    SqlSchemaParser,
)

scenarios("unit/knowledge/sql_data_extraction.feature")


@pytest.fixture
def ctx():
    return {}


# --- MySQL INSERT ---


@given("一段包含 INSERT INTO 的 MySQL dump")
def mysql_insert(ctx):
    ctx["text"] = """
CREATE TABLE `users` (
  `id` INT NOT NULL,
  `name` VARCHAR(100),
  `email` VARCHAR(200),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `users` (`id`, `name`, `email`)
VALUES (1, 'Alice', 'alice@example.com'),
(2, 'Bob', 'bob@example.com');
"""
    ctx["dialect"] = SqlDialect.MYSQL
    ctx["expected_table"] = "users"
    ctx["expected_count"] = 2


# --- PostgreSQL COPY ---


@given("一段包含 COPY FROM stdin 的 PostgreSQL dump")
def pg_copy(ctx):
    ctx["text"] = """
CREATE TABLE users (
  id serial NOT NULL,
  name VARCHAR(100),
  email VARCHAR(200),
  PRIMARY KEY (id)
);

COPY users (id, name, email) FROM stdin;
1\tAlice\talice@example.com
2\tBob\tbob@example.com
\\.
"""
    ctx["dialect"] = SqlDialect.POSTGRESQL
    ctx["expected_table"] = "users"
    ctx["expected_count"] = 2


@when("執行資料提取")
def extract_data(ctx):
    schemas = SqlSchemaParser.parse_tables(ctx["text"], ctx["dialect"])
    ctx["table_data"] = SqlDataExtractor.extract(ctx["text"], ctx["dialect"], schemas)


@then("應取得正確的表名與資料列")
def verify_table_data(ctx):
    table = ctx["expected_table"]
    assert table in ctx["table_data"]
    rows = ctx["table_data"][table]
    assert len(rows) == ctx["expected_count"]
    assert rows[0]["name"] == "Alice"
    assert rows[1]["name"] == "Bob"


# --- Multiple INSERTs merge ---


@given("一段包含同一表兩次 INSERT INTO 的 MySQL dump")
def mysql_multi_insert(ctx):
    ctx["text"] = """
CREATE TABLE `users` (
  `id` INT NOT NULL,
  `name` VARCHAR(100),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `users` (`id`, `name`) VALUES (1, 'Alice');
INSERT INTO `users` (`id`, `name`) VALUES (2, 'Bob');
"""
    ctx["dialect"] = SqlDialect.MYSQL
    ctx["expected_table"] = "users"


@then("該表的資料列應合併為完整集合")
def verify_merged(ctx):
    rows = ctx["table_data"][ctx["expected_table"]]
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert names == {"Alice", "Bob"}


# --- Special characters in values ---


@given("一段 INSERT INTO 的值包含引號和逗號")
def mysql_special_chars(ctx):
    ctx["text"] = """
CREATE TABLE `products` (
  `id` INT NOT NULL,
  `name` VARCHAR(255),
  `description` TEXT,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `products` (`id`, `name`, `description`)
VALUES (1, 'TV, 55 inch', 'A large TV');
"""
    ctx["dialect"] = SqlDialect.MYSQL
    ctx["expected_table"] = "products"


@then("應正確解析含特殊字元的值")
def verify_special_chars(ctx):
    rows = ctx["table_data"][ctx["expected_table"]]
    assert len(rows) == 1
    assert "TV" in rows[0]["name"]


# --- Parentheses inside quoted values ---


@given("一段 INSERT INTO 的值包含括號字串")
def mysql_paren_in_value(ctx):
    ctx["text"] = """
CREATE TABLE `products` (
  `id` INT NOT NULL,
  `name` VARCHAR(255),
  `description` TEXT,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `products` (`id`, `name`, `description`)
VALUES (1, 'T-Shirt (L)', 'cotton'),
(2, 'Pants', 'denim');
"""
    ctx["dialect"] = SqlDialect.MYSQL
    ctx["expected_table"] = "products"


@then("應正確解析含括號的值")
def verify_paren_values(ctx):
    rows = ctx["table_data"][ctx["expected_table"]]
    assert len(rows) == 2
    assert rows[0]["name"] == "T-Shirt (L)"
    assert rows[0]["description"] == "cotton"
    assert rows[1]["name"] == "Pants"


# --- Schema-qualified table names ---


@given("一段包含 schema-qualified 表名的 MySQL dump")
def mysql_schema_qualified(ctx):
    ctx["text"] = """
CREATE TABLE `mydb`.`users` (
  `id` INT NOT NULL,
  `name` VARCHAR(100),
  `email` VARCHAR(200),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `mydb`.`users` (`id`, `name`, `email`)
VALUES (1, 'Alice', 'alice@example.com'),
(2, 'Bob', 'bob@example.com');
"""
    ctx["dialect"] = SqlDialect.MYSQL
    ctx["expected_table"] = "users"
    ctx["expected_count"] = 2
