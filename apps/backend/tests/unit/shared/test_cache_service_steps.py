"""CacheService BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from redis.exceptions import RedisError

from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService
from src.infrastructure.cache.redis_cache_service import RedisCacheService

scenarios("unit/shared/cache_service.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Given ---


@given("一個空的快取服務")
def empty_cache(context):
    context["cache"] = InMemoryCacheService()


@given(parsers.parse('一個已有 key "{key}" 值為 "{value}" 的快取'))
def cache_with_entry(context, key, value):
    cache = InMemoryCacheService()
    _run(cache.set(key, value, ttl_seconds=300))
    context["cache"] = cache


@given("一個 Redis 連線異常的快取服務")
def broken_redis_cache(context):
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=RedisError("Connection refused"))
    mock_redis.setex = AsyncMock(side_effect=RedisError("Connection refused"))
    mock_redis.set = AsyncMock(side_effect=RedisError("Connection refused"))
    mock_redis.delete = AsyncMock(side_effect=RedisError("Connection refused"))
    context["cache"] = RedisCacheService(redis_client=mock_redis)


# --- When ---


@when(parsers.parse('設定 key "{key}" 值為 "{value}" 且 TTL 為 {ttl:d} 秒'))
def set_key(context, key, value, ttl):
    _run(context["cache"].set(key, value, ttl_seconds=ttl))


@when(parsers.parse('設定 key "{key}" 值為 "{value}" 且 TTL 已過期'))
def set_key_expired(context, key, value):
    cache = context["cache"]
    _run(cache.set(key, value, ttl_seconds=1))
    # Manually expire by overwriting internal store
    for k, (v, _) in cache._store.items():
        if k == key:
            cache._store[k] = (v, 0.0)  # already expired


@when(parsers.parse('刪除 key "{key}"'))
def delete_key(context, key):
    _run(context["cache"].delete(key))


@when(parsers.parse('查詢 key "{key}"'))
def query_key(context, key):
    context["result"] = _run(context["cache"].get(key))


# --- Then ---


@then(parsers.parse('查詢 key "{key}" 應回傳 "{expected}"'))
def verify_value(context, key, expected):
    result = _run(context["cache"].get(key))
    assert result == expected


@then(parsers.parse('查詢 key "{key}" 應回傳 None'))
def verify_none(context, key):
    result = _run(context["cache"].get(key))
    assert result is None


@then("應回傳 None 而非拋出例外")
def verify_none_no_exception(context):
    assert context["result"] is None
