import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.ratelimit.redis_rate_limiter import RedisRateLimiter

scenarios("unit/ratelimit/sliding_window_rate_limiter.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.zremrangebyscore = MagicMock(return_value=pipe)
    pipe.zadd = MagicMock(return_value=pipe)
    pipe.zcard = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[0, 1, 6, True])  # default: 6 in window
    redis.pipeline = MagicMock(return_value=pipe)
    redis.zrem = AsyncMock()
    redis.zrange = AsyncMock(return_value=[])
    return redis


@pytest.fixture
def rate_limiter(mock_redis):
    return RedisRateLimiter(redis_client=mock_redis)


@pytest.fixture
def context():
    return {}


@given(parsers.parse("限流設定為每分鐘 {limit:d} 次"))
def set_limit(context, limit):
    context["limit"] = limit


@given(parsers.parse("目前視窗內有 {count:d} 次請求"))
def set_current_count(context, mock_redis, count):
    context["count"] = count
    pipe = mock_redis.pipeline()
    # After zadd, total count = count + 1 (the new request)
    pipe.execute = AsyncMock(return_value=[0, 1, count + 1, True])


@given("Redis 連線已斷開")
def redis_disconnected(mock_redis):
    from redis.exceptions import ConnectionError as RedisConnectionError

    pipe = mock_redis.pipeline()
    pipe.execute = AsyncMock(side_effect=RedisConnectionError("Connection refused"))


@when("檢查限流")
def check_rate_limit(context, rate_limiter):
    context["result"] = _run(
        rate_limiter.check_rate_limit(
            key="test:key",
            limit=context["limit"],
            window_seconds=60,
        )
    )


@then("請求應被允許")
def request_allowed(context):
    assert context["result"].allowed is True


@then("請求應被拒絕")
def request_rejected(context):
    assert context["result"].allowed is False


@then(parsers.parse("剩餘次數應為 {remaining:d}"))
def remaining_count(context, remaining):
    assert context["result"].remaining == remaining


@then("retry_after 應大於 0")
def retry_after_positive(context):
    assert context["result"].retry_after is not None
    assert context["result"].retry_after > 0
