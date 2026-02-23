"""向量化 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.embedding.fake_embedding_service import (
    FakeEmbeddingService,
)

scenarios("unit/rag/vectorization.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def fake_embedding():
    return FakeEmbeddingService(vector_size=1536)


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.upsert = AsyncMock()
    store.ensure_collection = AsyncMock()
    return store


@given(parsers.parse("{count:d} 個文字 chunks"))
def text_chunks(context, count):
    context["chunks"] = [f"chunk content {i}" for i in range(count)]


@given(parsers.parse('{count:d} 個文字 chunks 屬於 tenant "{tid}"'))
def text_chunks_with_tenant(context, count, tid):
    context["chunks"] = [f"chunk content {i}" for i in range(count)]
    context["tenant_id"] = tid
    context["chunk_ids"] = [f"chunk-{i}" for i in range(count)]


@given(parsers.parse('一段文字 "{text}"'))
def single_text(context, text):
    context["text"] = text


@when("執行向量化")
def do_vectorize(context, fake_embedding):
    context["vectors"] = _run(
        fake_embedding.embed_texts(context["chunks"])
    )


@when(parsers.parse('執行向量 upsert 到 collection "{collection}"'))
def do_upsert(context, fake_embedding, mock_vector_store):
    vectors = _run(fake_embedding.embed_texts(context["chunks"]))
    payloads = [
        {
            "tenant_id": context["tenant_id"],
            "content": c,
        }
        for c in context["chunks"]
    ]
    _run(
        mock_vector_store.upsert(
            collection="kb_test",
            ids=context["chunk_ids"],
            vectors=vectors,
            payloads=payloads,
        )
    )
    context["mock_vector_store"] = mock_vector_store


@when("使用 FakeEmbeddingService 進行 embed")
def do_fake_embed(context, fake_embedding):
    context["vector"] = _run(
        fake_embedding.embed_query(context["text"])
    )


@then(parsers.parse("產生 {count:d} 個 {dim:d} 維向量"))
def vector_count_and_dim(context, count, dim):
    assert len(context["vectors"]) == count
    for v in context["vectors"]:
        assert len(v) == dim


@then(
    parsers.parse(
        'upsert 的每筆 payload 包含 tenant_id "{tid}"'
    )
)
def upsert_has_tenant_id(context, tid):
    call_args = context["mock_vector_store"].upsert.call_args
    payloads = call_args.kwargs["payloads"]
    for payload in payloads:
        assert payload["tenant_id"] == tid


@then(parsers.parse("回傳 {dim:d} 維向量"))
def vector_dim(context, dim):
    assert len(context["vector"]) == dim
