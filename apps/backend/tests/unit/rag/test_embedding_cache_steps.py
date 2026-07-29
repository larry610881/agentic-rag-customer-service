"""Embedding 查詢快取 BDD Steps — Issue #52 E1"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.embedding.cached_embedding_service import (
    CachedEmbeddingService,
    decode_vector,
    encode_vector,
)

scenarios("unit/rag/embedding_cache.feature")

_VECTOR = [0.1, -0.25, 3.5, 0.0]
_QUERY = "怎麼退貨"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_service(cache=None, model="text-embedding-3-large"):
    inner = AsyncMock()
    inner.embed_query = AsyncMock(return_value=list(_VECTOR))
    inner.embed_texts = AsyncMock(return_value=[list(_VECTOR)] * 2)
    cache = cache if cache is not None else AsyncMock()
    return CachedEmbeddingService(inner=inner, cache=cache, model=model), inner, cache


@pytest.fixture
def context():
    return {}


@given('快取中沒有查詢 "怎麼退貨" 的向量')
def cache_miss(context):
    service, inner, cache = _make_service()
    cache.get = AsyncMock(return_value=None)
    context.update(service=service, inner=inner, cache=cache)


@given('快取中已存在查詢 "怎麼退貨" 的向量')
def cache_hit(context):
    cached_vector = [9.0, 8.0, 7.0, 6.0]
    service, inner, cache = _make_service()
    cache.get = AsyncMock(return_value=encode_vector(cached_vector))
    context.update(
        service=service, inner=inner, cache=cache, cached_vector=cached_vector
    )


@given("快取服務讀取時會回傳 None")
def cache_get_fails(context):
    # RedisCacheService 對 RedisError fail-open 回 None，decorator 視為未命中
    service, inner, cache = _make_service()
    cache.get = AsyncMock(return_value=None)
    context.update(service=service, inner=inner, cache=cache)


@given('快取中查詢 "怎麼退貨" 的值是毀損的資料')
def cache_corrupted(context):
    service, inner, cache = _make_service()
    cache.get = AsyncMock(return_value="not-valid-base64!!!")
    context.update(service=service, inner=inner, cache=cache)


@given("兩個使用不同模型的快取 embedding 服務")
def two_models(context):
    service_a, _, cache_a = _make_service(model="text-embedding-3-large")
    service_b, _, cache_b = _make_service(model="text-embedding-3-small")
    cache_a.get = AsyncMock(return_value=None)
    cache_b.get = AsyncMock(return_value=None)
    context.update(
        service_a=service_a, cache_a=cache_a, service_b=service_b, cache_b=cache_b
    )


@given("快取中沒有任何資料")
def empty_cache(context):
    service, inner, cache = _make_service()
    cache.get = AsyncMock(return_value=None)
    context.update(service=service, inner=inner, cache=cache)


@when('我對 "怎麼退貨" 執行 embed_query')
def do_embed_query(context):
    context["result"] = _run(context["service"].embed_query(_QUERY))


@when('我分別對 "怎麼退貨" 執行 embed_query')
def do_embed_query_both(context):
    _run(context["service_a"].embed_query(_QUERY))
    _run(context["service_b"].embed_query(_QUERY))


@when('我對 "  怎麼退貨  " 執行 embed_query 後再對 "怎麼退貨" 執行')
def do_embed_query_whitespace(context):
    store: dict[str, str] = {}
    cache = context["cache"]
    cache.get = AsyncMock(side_effect=lambda key: store.get(key))

    async def _set(key, value, ttl_seconds=None):
        store[key] = value

    cache.set = AsyncMock(side_effect=_set)
    _run(context["service"].embed_query(f"  {_QUERY}  "))
    context["result"] = _run(context["service"].embed_query(_QUERY))


@when("我對多筆文字執行 embed_texts")
def do_embed_texts(context):
    context["result"] = _run(context["service"].embed_texts(["甲", "乙"]))


@then("應呼叫內層 embedding 服務一次")
def inner_called_once(context):
    assert context["inner"].embed_query.await_count == 1


@then("不應呼叫內層 embedding 服務")
def inner_not_called(context):
    context["inner"].embed_query.assert_not_awaited()


@then("應將向量以 TTL 寫入快取")
def cache_written_with_ttl(context):
    context["cache"].set.assert_awaited_once()
    kwargs = context["cache"].set.await_args.kwargs
    args = context["cache"].set.await_args.args
    ttl = kwargs.get("ttl_seconds") or (args[2] if len(args) > 2 else None)
    assert ttl is not None and ttl > 0
    value = kwargs.get("value") or args[1]
    assert decode_vector(value) == pytest.approx(_VECTOR)


@then("回傳的向量應與內層服務結果一致")
def result_matches_inner(context):
    assert context["result"] == pytest.approx(_VECTOR)


@then("回傳的向量應與快取內容一致")
def result_matches_cache(context):
    assert context["result"] == pytest.approx(context["cached_vector"])


@then("兩者寫入快取的鍵應不相同")
def keys_differ(context):
    key_a = context["cache_a"].set.await_args.args[0]
    key_b = context["cache_b"].set.await_args.args[0]
    assert key_a != key_b


@then("內層 embedding 服務只應被呼叫一次")
def inner_called_once_after_two(context):
    assert context["inner"].embed_query.await_count == 1
    assert context["result"] == pytest.approx(_VECTOR)


@then("應直接委派內層服務且不讀寫快取")
def texts_delegated(context):
    context["inner"].embed_texts.assert_awaited_once()
    context["cache"].get.assert_not_awaited()
    context["cache"].set.assert_not_awaited()
