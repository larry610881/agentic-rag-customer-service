"""文件分塊 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.text_splitter.recursive_text_splitter_service import (
    RecursiveTextSplitterService,
)

scenarios("unit/knowledge/document_chunking.feature")


@pytest.fixture
def context():
    return {}


@pytest.fixture
def splitter_service():
    return RecursiveTextSplitterService(chunk_size=500, chunk_overlap=100)


@given(parsers.parse("一段 {length:d} 字元的短文字"))
def short_text(context, length):
    context["text"] = "A" * length


@given(parsers.parse("一段 {length:d} 字元的長文字"))
def long_text(context, length):
    # Create text with natural word boundaries for better splitting
    word = "Hello world this is a test sentence. "
    context["text"] = (word * (length // len(word) + 1))[:length]


@when("執行分塊處理")
def do_split(context, splitter_service):
    context["chunks"] = splitter_service.split(
        context["text"], "doc-default", "tenant-default"
    )


@when(
    parsers.parse(
        '以 document_id "{doc_id}" 和 tenant_id "{tid}" 執行分塊'
    )
)
def do_split_with_ids(context, splitter_service, doc_id, tid):
    context["chunks"] = splitter_service.split(
        context["text"], doc_id, tid
    )


@then(parsers.parse("產生 {count:d} 個 chunk"))
def chunk_count_exact(context, count):
    assert len(context["chunks"]) == count


@then(parsers.parse("產生至少 {count:d} 個 chunks"))
def chunk_count_min(context, count):
    assert len(context["chunks"]) >= count


@then(parsers.parse("每個 chunk 不超過 {max_size:d} 字元"))
def chunk_max_size(context, max_size):
    for chunk in context["chunks"]:
        assert len(chunk.content) <= max_size


@then(parsers.parse('每個 chunk 的 document_id 為 "{doc_id}"'))
def chunk_doc_id(context, doc_id):
    for chunk in context["chunks"]:
        assert chunk.document_id == doc_id


@then(parsers.parse('每個 chunk 的 tenant_id 為 "{tid}"'))
def chunk_tenant_id(context, tid):
    for chunk in context["chunks"]:
        assert chunk.tenant_id == tid
