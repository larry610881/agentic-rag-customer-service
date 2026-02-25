"""向量化 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.embedding.fake_embedding_service import (
    FakeEmbeddingService,
)
from src.infrastructure.embedding.openai_embedding_service import (
    OpenAIEmbeddingService,
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


# --- OpenAI Embedding batching + retry scenarios ---


@pytest.fixture
def mock_openai_response():
    """建立模擬 OpenAI API 回應的工廠函式"""
    def _make(count: int):
        return {
            "data": [{"embedding": [0.1] * 1536} for _ in range(count)]
        }
    return _make


@given("101 個文字 chunks 使用 OpenAI embedding")
def openai_101_chunks(context, mock_openai_response):
    context["chunks"] = [f"chunk {i}" for i in range(101)]
    context["api_call_count"] = 0

    original_response = mock_openai_response

    async def mock_post(url, **kwargs):
        context["api_call_count"] = context.get("api_call_count", 0) + 1
        batch_size = len(kwargs["json"]["input"])
        resp = MagicMock()
        resp.json.return_value = original_response(batch_size)
        resp.raise_for_status = MagicMock()
        return resp

    context["mock_post"] = mock_post


@given("3 個文字 chunks 使用 OpenAI embedding 且首次呼叫失敗")
def openai_3_chunks_with_failure(context, mock_openai_response):
    context["chunks"] = [f"chunk {i}" for i in range(3)]
    context["api_call_count"] = 0

    async def mock_post(url, **kwargs):
        context["api_call_count"] = context.get("api_call_count", 0) + 1
        if context["api_call_count"] == 1:
            raise RuntimeError("API timeout")
        batch_size = len(kwargs["json"]["input"])
        resp = MagicMock()
        resp.json.return_value = mock_openai_response(batch_size)
        resp.raise_for_status = MagicMock()
        return resp

    context["mock_post"] = mock_post


@when("執行 OpenAI 向量化")
def do_openai_vectorize(context):
    service = OpenAIEmbeddingService(api_key="test-key")

    async def _execute():
        mock_client = AsyncMock()
        mock_client.post = context["mock_post"]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                return await service.embed_texts(context["chunks"])

    context["vectors"] = _run(_execute())


@then(parsers.parse("API 呼叫次數為 {count:d}"))
def verify_api_call_count(context, count):
    assert context["api_call_count"] == count


@then(parsers.parse("產生 {count:d} 個向量且 API 呼叫次數為 {api_count:d}"))
def verify_vectors_and_calls(context, count, api_count):
    assert len(context["vectors"]) == count
    assert context["api_call_count"] == api_count
