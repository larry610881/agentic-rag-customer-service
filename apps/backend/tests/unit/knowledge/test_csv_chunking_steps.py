"""CSV 分塊 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.text_splitter.csv_row_text_splitter_service import (
    CSVRowTextSplitterService,
)

scenarios("unit/knowledge/csv_chunking.feature")


@pytest.fixture
def ctx():
    return {}


@given(
    parsers.parse(
        "一段包含 header 和 {rows:d} 行資料的 CSV 文字且 chunk_size 為 {size:d}"
    )
)
def csv_with_rows(ctx, rows, size):
    header = "name,price,category"
    data = [f"item_{i},100,cat_{i}" for i in range(rows)]
    ctx["text"] = header + "\n" + "\n".join(data)
    ctx["header"] = header
    ctx["splitter"] = CSVRowTextSplitterService(chunk_size=size)


@given(
    parsers.parse(
        "一段包含 header 和一行超長資料的 CSV 文字且 chunk_size 為 {size:d}"
    )
)
def csv_with_oversized_row(ctx, size):
    header = "name,price"
    long_row = "x" * 100 + ",999"
    ctx["text"] = header + "\n" + long_row
    ctx["header"] = header
    ctx["long_row"] = long_row
    ctx["splitter"] = CSVRowTextSplitterService(chunk_size=size)


@given("一段只有 header 的 CSV 文字")
def csv_header_only(ctx):
    ctx["text"] = "name,price,category"
    ctx["header"] = "name,price,category"
    ctx["splitter"] = CSVRowTextSplitterService(chunk_size=200)


@when("執行 CSV 分塊處理")
def do_csv_split(ctx):
    ctx["chunks"] = ctx["splitter"].split(
        ctx["text"], "doc-csv", "tenant-csv", content_type="text/csv"
    )


@then("每個 chunk 中的資料行都是完整的一行")
def rows_are_intact(ctx):
    for chunk in ctx["chunks"]:
        lines = chunk.content.split("\n")
        # Skip header line (first line)
        for line in lines[1:]:
            if line.strip():
                assert "," in line, f"Row seems truncated: {line}"


@then("每個 chunk 的第一行都是 header")
def each_chunk_starts_with_header(ctx):
    header = ctx["header"]
    for chunk in ctx["chunks"]:
        first_line = chunk.content.split("\n")[0]
        assert first_line == header


@then(parsers.parse("產生 {count:d} 個 CSV chunk"))
def csv_chunk_count(ctx, count):
    assert len(ctx["chunks"]) == count


@then("該 chunk 包含 header 和該超長行")
def chunk_has_header_and_long_row(ctx):
    chunk = ctx["chunks"][0]
    assert chunk.content.startswith(ctx["header"])
    assert ctx["long_row"] in chunk.content
