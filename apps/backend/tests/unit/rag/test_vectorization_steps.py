"""向量化 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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


# --- 429 Retry-After + adaptive batch size scenarios ---


def _make_429_response(retry_after: str | None = None) -> httpx.Response:
    """Build a mock httpx.Response that triggers HTTPStatusError with 429."""
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    headers = {"Retry-After": retry_after} if retry_after else {}
    response = httpx.Response(429, request=request, headers=headers)
    return response


@given("3 個文字 chunks 使用 OpenAI embedding 且首次回傳 429 帶 Retry-After 2")
def openai_3_chunks_429_retry_after(context, mock_openai_response):
    context["chunks"] = [f"chunk {i}" for i in range(3)]
    context["api_call_count"] = 0

    async def mock_post(url, **kwargs):
        context["api_call_count"] = context.get("api_call_count", 0) + 1
        if context["api_call_count"] == 1:
            resp_429 = _make_429_response(retry_after="2")
            raise httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=resp_429.request,
                response=resp_429,
            )
        batch_size = len(kwargs["json"]["input"])
        resp = MagicMock()
        resp.json.return_value = mock_openai_response(batch_size)
        resp.raise_for_status = MagicMock()
        return resp

    context["mock_post"] = mock_post


@when("執行 OpenAI 向量化並記錄等待時間")
def do_openai_vectorize_record_sleep(context):
    service = OpenAIEmbeddingService(api_key="test-key")
    sleep_values: list[float] = []

    async def _execute():
        mock_client = AsyncMock()
        mock_client.post = context["mock_post"]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def mock_sleep(seconds):
            sleep_values.append(seconds)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                return await service.embed_texts(context["chunks"])

    context["vectors"] = _run(_execute())
    context["sleep_values"] = sleep_values


@then("等待時間應至少為 2 秒")
def verify_retry_after_wait(context):
    # The first sleep should be the Retry-After value (2.0)
    retry_sleeps = [s for s in context["sleep_values"] if s >= 2.0]
    assert len(retry_sleeps) >= 1, (
        f"Expected at least one sleep >= 2s, got: {context['sleep_values']}"
    )


@given("80 個文字 chunks 使用 OpenAI embedding 且首批回傳 429")
def openai_80_chunks_429_first_batch(context, mock_openai_response):
    context["chunks"] = [f"chunk {i}" for i in range(80)]
    context["api_call_count"] = 0
    context["batch_sizes"] = []

    async def mock_post(url, **kwargs):
        context["api_call_count"] = context.get("api_call_count", 0) + 1
        batch_size = len(kwargs["json"]["input"])
        context["batch_sizes"].append(batch_size)
        # First call: 429 (the first batch of 50)
        if context["api_call_count"] == 1:
            resp_429 = _make_429_response(retry_after="1")
            raise httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=resp_429.request,
                response=resp_429,
            )
        resp = MagicMock()
        resp.json.return_value = mock_openai_response(batch_size)
        resp.raise_for_status = MagicMock()
        return resp

    context["mock_post"] = mock_post


@then("所有 80 個 chunks 向量化成功")
def verify_80_chunks(context):
    assert len(context["vectors"]) == 80


@then("後續 batch 的 chunk 數應小於初始 batch size")
def verify_batch_size_reduced(context):
    # batch_sizes tracks actual API calls:
    # call 1: 50 (429 fail)
    # call 2: 50 (retry success)
    # call 3+: should use reduced batch size (25)
    batch_sizes = context["batch_sizes"]
    assert len(batch_sizes) >= 3, f"Expected at least 3 API calls, got {batch_sizes}"
    # After first batch (50) succeeded with 429, subsequent batches should be smaller
    subsequent_sizes = batch_sizes[2:]  # skip the 429 call and its retry
    for size in subsequent_sizes:
        assert size < 50, (
            f"Expected reduced batch size < 50, got {size} in {batch_sizes}"
        )
