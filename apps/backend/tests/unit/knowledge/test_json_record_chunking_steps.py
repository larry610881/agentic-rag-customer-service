"""JSON Record-Based Chunking BDD Step Definitions"""

import json
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.text_splitter.json_record_text_splitter_service import (
    JsonRecordTextSplitterService,
)

scenarios("unit/knowledge/json_record_chunking.feature")


@pytest.fixture
def ctx():
    return {}


@given(
    parsers.parse(
        "一段包含 {count:d} 筆記錄的 JSON array 且 chunk_size 為 {size:d}"
    )
)
def json_array_with_records(ctx, count, size):
    records = [
        {
            "name": f"講師_{i}",
            "description": f"從事廚藝工作{i}年的專業講師",
            "specialty": f"專長_{i}",
        }
        for i in range(count)
    ]
    ctx["text"] = json.dumps(records, ensure_ascii=False)
    ctx["record_count"] = count
    ctx["splitter"] = JsonRecordTextSplitterService(chunk_size=size)


@given(
    parsers.parse(
        "一段包含 {count:d} 筆小記錄的 JSON array 且 chunk_size 為 {size:d}"
    )
)
def json_array_with_small_records(ctx, count, size):
    records = [
        {"name": f"item_{i}", "price": 100}
        for i in range(count)
    ]
    ctx["text"] = json.dumps(records, ensure_ascii=False)
    ctx["record_count"] = count
    ctx["splitter"] = JsonRecordTextSplitterService(chunk_size=size)


@given(
    parsers.parse(
        "一段包含 {count:d} 筆超大記錄的 JSON array 且 chunk_size 為 {size:d}"
    )
)
def json_array_with_oversized_record(ctx, count, size):
    records = [
        {"name": "超長講師名", "description": "x" * 200}
    ]
    ctx["text"] = json.dumps(records, ensure_ascii=False)
    ctx["record_count"] = count
    ctx["splitter"] = JsonRecordTextSplitterService(chunk_size=size)


@given(
    parsers.parse(
        "一段包含巢狀 array 的 JSON object 且 chunk_size 為 {size:d}"
    )
)
def json_nested_object(ctx, size):
    data = {
        "total": 3,
        "items": [
            {"name": f"商品_{i}", "price": i * 100}
            for i in range(3)
        ],
    }
    ctx["text"] = json.dumps(data, ensure_ascii=False)
    ctx["record_count"] = 3
    ctx["splitter"] = JsonRecordTextSplitterService(chunk_size=size)


@given("一段不含 array 的 JSON object")
def json_plain_object(ctx):
    data = {"name": "test", "value": 42}
    ctx["text"] = json.dumps(data, ensure_ascii=False)
    fallback = MagicMock()
    fallback.split.return_value = [MagicMock(content="fallback")]
    ctx["fallback"] = fallback
    ctx["splitter"] = JsonRecordTextSplitterService(
        chunk_size=200, fallback=fallback
    )


@when("執行 JSON 分塊處理")
def do_json_split(ctx):
    ctx["chunks"] = ctx["splitter"].split(
        ctx["text"], "doc-json", "tenant-json", content_type="application/json"
    )


@then("每個 chunk 都包含完整的記錄（不會斷在欄位中間）")
def records_are_intact(ctx):
    assert len(ctx["chunks"]) > 0
    for chunk in ctx["chunks"]:
        # Each record block should have "name:" as a complete field
        records_in_chunk = chunk.content.split("\n\n")
        for record_text in records_in_chunk:
            lines = record_text.strip().split("\n")
            for line in lines:
                assert ": " in line, f"Line seems truncated: {line}"


@then(parsers.parse("產生 {count:d} 個 JSON chunk"))
def json_chunk_count(ctx, count):
    assert len(ctx["chunks"]) == count


@then(parsers.parse("該 chunk 包含全部 {count:d} 筆記錄"))
def chunk_contains_all_records(ctx, count):
    chunk = ctx["chunks"][0]
    # Count record blocks separated by double newlines
    records = chunk.content.split("\n\n")
    assert len(records) == count


@then("該 chunk 的 metadata 包含 record_start 和 record_end")
def chunk_has_record_metadata(ctx):
    chunk = ctx["chunks"][0]
    assert "record_start" in chunk.metadata
    assert "record_end" in chunk.metadata
    assert chunk.metadata["record_start"] == 0
    assert chunk.metadata["record_end"] == 0


@then("使用 fallback splitter 處理")
def fallback_used(ctx):
    ctx["fallback"].split.assert_called_once()
