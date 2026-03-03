"""SQL Preprocessing BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.knowledge.services import SQLCleaningService, TextPreprocessor

scenarios("unit/knowledge/sql_preprocessing.feature")


@pytest.fixture
def ctx():
    return {}


# --- Single-line comments ---


@given("一段包含 -- 單行註解的 SQL 文字")
def sql_with_line_comments(ctx):
    ctx["text"] = """-- This is a comment
CREATE TABLE users (id INT);
-- Another comment
INSERT INTO users (id) VALUES (1);
"""


@given("一段包含 -- 註解的 SQL 文字")
def sql_with_line_comments_for_preprocessor(ctx):
    ctx["text"] = """-- This is a comment
CREATE TABLE users (id INT);
INSERT INTO users (id) VALUES (1);
"""


@when("執行 SQL 清洗")
def do_sql_clean(ctx):
    ctx["result"] = SQLCleaningService.clean(ctx["text"])


@then("結果不應包含 -- 開頭的註解行")
def verify_no_line_comments(ctx):
    for line in ctx["result"].split("\n"):
        stripped = line.strip()
        if stripped:
            assert not stripped.startswith("--"), f"Found comment: {stripped}"


# --- Multi-line comments ---


@given("一段包含 /* */ 多行註解的 SQL 文字")
def sql_with_block_comments(ctx):
    ctx["text"] = """/* Multi-line
   comment here */
CREATE TABLE users (id INT);
/* Another comment */
INSERT INTO users (id) VALUES (1);
"""


@then("結果不應包含多行註解")
def verify_no_block_comments(ctx):
    assert "/*" not in ctx["result"]
    assert "*/" not in ctx["result"]
    assert "CREATE TABLE" in ctx["result"]


# --- SET statements ---


@given("一段包含 SET 語句的 SQL 文字")
def sql_with_set(ctx):
    ctx["text"] = """SET NAMES utf8mb4;
SET character_set_client = utf8mb4;
CREATE TABLE users (id INT);
INSERT INTO users (id) VALUES (1);
"""


@then("結果不應包含 SET 語句")
def verify_no_set(ctx):
    for line in ctx["result"].split("\n"):
        stripped = line.strip()
        if stripped:
            assert not stripped.upper().startswith("SET "), f"Found SET: {stripped}"


# --- LOCK TABLES ---


@given("一段包含 LOCK TABLES 和 UNLOCK TABLES 的 SQL 文字")
def sql_with_lock(ctx):
    ctx["text"] = """LOCK TABLES `users` WRITE;
INSERT INTO users (id) VALUES (1);
UNLOCK TABLES;
"""


@then("結果不應包含 LOCK TABLES 和 UNLOCK TABLES 語句")
def verify_no_lock(ctx):
    result_upper = ctx["result"].upper()
    assert "LOCK TABLES" not in result_upper
    assert "UNLOCK TABLES" not in result_upper


# --- TextPreprocessor integration ---


@when("以 application/sql content_type 執行文字前處理")
def do_preprocess_sql(ctx):
    ctx["result"] = TextPreprocessor.preprocess(ctx["text"], "application/sql")
