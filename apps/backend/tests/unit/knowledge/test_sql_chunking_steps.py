"""SQL Chunking BDD Step Definitions"""

from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.text_splitter.content_aware_text_splitter_service import (
    ContentAwareTextSplitterService,
)
from src.infrastructure.text_splitter.sql_dump_text_splitter_service import (
    SqlDumpTextSplitterService,
)

scenarios("unit/knowledge/sql_chunking.feature")


@pytest.fixture
def ctx():
    return {}


_MYSQL_DUMP_TWO_TABLES = """\
CREATE TABLE `customers` (
  `id` INT NOT NULL,
  `name` VARCHAR(100),
  `email` VARCHAR(200),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE `orders` (
  `id` INT NOT NULL,
  `customer_id` INT NOT NULL,
  `total` DECIMAL(10,2),
  PRIMARY KEY (`id`),
  FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`)
) ENGINE=InnoDB;

INSERT INTO `customers` (`id`, `name`, `email`)
VALUES (1, 'Alice', 'alice@example.com'),
(2, 'Bob', 'bob@example.com');
INSERT INTO `orders` (`id`, `customer_id`, `total`)
VALUES (101, 1, 99.99), (102, 2, 49.50);
"""


@given(parsers.parse("一段包含兩張表的完整 MySQL dump 且 chunk_size 為 {size:d}"))
def two_table_dump(ctx, size):
    ctx["text"] = _MYSQL_DUMP_TWO_TABLES
    ctx["splitter"] = SqlDumpTextSplitterService(chunk_size=size)


@given("一段包含 CREATE TABLE 但無 INSERT 資料的 SQL dump")
def empty_table_dump(ctx):
    ctx["text"] = """
CREATE TABLE `empty_table` (
  `id` INT NOT NULL,
  `name` VARCHAR(100),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
"""
    ctx["splitter"] = SqlDumpTextSplitterService(chunk_size=500)


@given("一個 ContentAwareTextSplitterService 已註冊 SQL 策略")
def content_aware_with_sql(ctx):
    ctx["sql_strategy"] = MagicMock()
    ctx["sql_strategy"].split.return_value = []
    ctx["default_strategy"] = MagicMock()
    ctx["default_strategy"].split.return_value = []
    ctx["service"] = ContentAwareTextSplitterService(
        strategies={"application/sql": ctx["sql_strategy"]},
        default=ctx["default_strategy"],
    )


@when("執行 SQL 分塊處理")
def do_sql_split(ctx):
    ctx["chunks"] = ctx["splitter"].split(
        ctx["text"], "doc-sql", "tenant-sql", content_type="application/sql"
    )


@when(parsers.parse('以 content_type "{ct}" 執行分塊'))
def do_content_aware_split(ctx, ct):
    ctx["service"].split("dummy", "doc-1", "t-1", content_type=ct)


@then("應產生按表分組的 chunk")
def verify_table_grouped(ctx):
    chunks = ctx["chunks"]
    assert len(chunks) >= 2
    table_names = {c.metadata["table_name"] for c in chunks}
    assert "customers" in table_names
    assert "orders" in table_names


@then("每個 chunk 的第一行包含表頭資訊")
def verify_table_header(ctx):
    for chunk in ctx["chunks"]:
        first_line = chunk.content.split("\n")[0]
        assert first_line.startswith("[Table:")


@then("每個 chunk 的 metadata 應包含 table_name 和 row_start 和 row_end")
def verify_metadata(ctx):
    for chunk in ctx["chunks"]:
        assert "table_name" in chunk.metadata
        assert "row_start" in chunk.metadata
        assert "row_end" in chunk.metadata


@then(parsers.parse("應產生 {count:d} 個 chunk"))
def verify_chunk_count(ctx, count):
    assert len(ctx["chunks"]) == count


@then("SQL 策略被呼叫")
def verify_sql_called(ctx):
    ctx["sql_strategy"].split.assert_called_once()
