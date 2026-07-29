"""換版啟動暖機 BDD Steps — Issue #53"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.warmup import run_startup_warmup

scenarios("unit/platform/startup_warmup.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_deps(milvus_raises=False, milvus_hangs=False):
    session = AsyncMock()
    session.execute = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield session

    vector_store = MagicMock()
    if milvus_hangs:
        async def _hang():
            await asyncio.sleep(3600)
        vector_store.ping = AsyncMock(side_effect=_hang)
    elif milvus_raises:
        vector_store.ping = AsyncMock(side_effect=RuntimeError("milvus down"))
    else:
        vector_store.ping = AsyncMock()

    cache_service = AsyncMock()
    cache_service.get = AsyncMock(return_value=None)
    return session, session_factory, vector_store, cache_service


@given("DB、Milvus、Redis 服務皆正常")
def all_healthy(context):
    context["deps"] = _make_deps()


@given("Milvus 探測會拋出例外")
def milvus_fails(context):
    context["deps"] = _make_deps(milvus_raises=True)


@given("Milvus 探測會永久卡住")
def milvus_hangs(context):
    context["deps"] = _make_deps(milvus_hangs=True)


@when("執行啟動暖機")
def do_warmup(context):
    session, factory, vs, cache = context["deps"]
    context["result"] = _run(run_startup_warmup(
        session_factory=factory, vector_store=vs, cache_service=cache,
    ))


@when("執行啟動暖機且逾時上限為 0.2 秒")
def do_warmup_with_timeout(context):
    session, factory, vs, cache = context["deps"]
    context["result"] = _run(run_startup_warmup(
        session_factory=factory, vector_store=vs, cache_service=cache,
        timeout_seconds=0.2,
    ))


@then("DB 應被探測一次")
def db_probed(context):
    session = context["deps"][0]
    session.execute.assert_awaited_once()


@then("Milvus 應被探測一次")
def milvus_probed(context):
    context["deps"][2].ping.assert_awaited_once()


@then("Redis 應被探測一次")
def redis_probed(context):
    context["deps"][3].get.assert_awaited_once()


@then("暖機應正常返回不拋例外")
def warmup_returns(context):
    assert "result" in context  # _run 沒拋例外即通過
