"""BDD steps: Conversation Lock — RedisConversationLock 單元測試"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.concurrency.redis_conversation_lock import (
    RedisConversationLock,
)

scenarios("unit/agent/conversation_lock.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# ── Scenario 1: 第一個請求取得鎖並正常執行 ──


@given("一個空閒的 conversation")
def idle_conversation(context):
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)  # NX succeeds
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    context["redis"] = redis
    context["lock"] = RedisConversationLock(redis)
    context["lock_key"] = "conv_lock:test-conv-1"


@when("使用者送出訊息")
def user_sends_message(context):
    async def _acquire():
        async with context["lock"].acquire(context["lock_key"]) as acquired:
            context["acquired"] = acquired
    _run(_acquire())


@then("應成功取得鎖並執行 agent")
def lock_acquired(context):
    assert context["acquired"] is True
    context["redis"].set.assert_called_once()


# ── Scenario 2: 第二個請求被拒絕 ──


@given("一個正在處理中的 conversation")
def busy_conversation(context):
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=None)  # NX fails — lock held
    context["redis"] = redis
    context["lock"] = RedisConversationLock(redis)
    context["lock_key"] = "conv_lock:test-conv-2"


@when("同一使用者再次送出訊息")
def second_request(context):
    async def _acquire():
        async with context["lock"].acquire(context["lock_key"]) as acquired:
            context["acquired"] = acquired
    _run(_acquire())


@then("應回傳 busy_reply_message 而非執行 agent")
def rejected(context):
    assert context["acquired"] is False


# ── Scenario 3: Redis 斷線時降級為無鎖 ──


@given("Redis 連線中斷")
def redis_down(context):
    redis = AsyncMock()
    redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
    context["redis"] = redis
    context["lock"] = RedisConversationLock(redis)
    context["lock_key"] = "conv_lock:test-conv-3"


@then("應正常執行 agent（降級無鎖）")
def degraded_no_lock(context):
    assert context["acquired"] is True


# ── Scenario 4: Agent 執行完畢後鎖自動釋放 ──


@when("agent 執行完畢")
def agent_finishes(context):
    # Set up redis to track lock value for ownership check
    lock_value_store = {}

    async def fake_set(key, value, nx=False, ex=None):
        lock_value_store["value"] = value
        return True

    async def fake_get(key):
        v = lock_value_store.get("value")
        return v.encode() if v else None

    context["redis"].set = AsyncMock(side_effect=fake_set)
    context["redis"].get = AsyncMock(side_effect=fake_get)
    context["redis"].delete = AsyncMock()

    # Re-create lock with updated redis mock
    context["lock"] = RedisConversationLock(context["redis"])

    async def _acquire_and_release():
        async with context["lock"].acquire(context["lock_key"]) as acquired:
            context["acquired"] = acquired
    _run(_acquire_and_release())


@then("鎖應被釋放，下一個請求可取得")
def lock_released(context):
    assert context["acquired"] is True
    context["redis"].delete.assert_called_once_with(context["lock_key"])
