"""Worker 設定快取 BDD Steps — Issue #52 E2"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.bot.worker_config import WorkerConfig
from src.infrastructure.db.repositories.cached_worker_config_repository import (
    CachedWorkerConfigRepository,
    invalidate_worker_config_cache,
)

scenarios("unit/agent/worker_config_cache.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _reset_cache():
    invalidate_worker_config_cache()
    yield
    invalidate_worker_config_cache()


@pytest.fixture
def context():
    return {}


def _workers(bot_id, n=2):
    return [WorkerConfig(bot_id=bot_id, name=f"w{i}") for i in range(n)]


def _make_repo(workers_by_bot):
    inner = AsyncMock()
    inner.find_by_bot_id = AsyncMock(
        side_effect=lambda bot_id: workers_by_bot.get(bot_id, [])
    )
    inner.find_by_id = AsyncMock(return_value=None)
    inner.save = AsyncMock()
    inner.delete = AsyncMock()
    return CachedWorkerConfigRepository(inner=inner), inner


@given('bot "B001" 已設定兩個 worker')
def bot_with_workers(context):
    repo, inner = _make_repo({"B001": _workers("B001")})
    context.update(repo=repo, inner=inner)


@given('bot "B001" 與 bot "B002" 各有 worker 設定')
def two_bots(context):
    repo, inner = _make_repo(
        {"B001": _workers("B001"), "B002": _workers("B002", n=1)}
    )
    context.update(repo=repo, inner=inner)


@given('bot "B001" 的 worker 設定已被快取')
def bot_cached(context):
    bot_with_workers(context)
    _run(context["repo"].find_by_bot_id("B001"))
    assert context["inner"].find_by_bot_id.await_count == 1


@when('我連續查詢 bot "B001" 的 worker 設定兩次')
def query_twice(context):
    context["first"] = _run(context["repo"].find_by_bot_id("B001"))
    context["second"] = _run(context["repo"].find_by_bot_id("B001"))


@when("我分別查詢兩個 bot 的 worker 設定")
def query_two_bots(context):
    context["first"] = _run(context["repo"].find_by_bot_id("B001"))
    context["second"] = _run(context["repo"].find_by_bot_id("B002"))


@when('我儲存 worker 設定後再次查詢 bot "B001"')
def save_then_query(context):
    _run(context["repo"].save(WorkerConfig(bot_id="B001", name="new")))
    context["after"] = _run(context["repo"].find_by_bot_id("B001"))


@when('我刪除 worker 後再次查詢 bot "B001"')
def delete_then_query(context):
    _run(context["repo"].delete("some-worker-id"))
    context["after"] = _run(context["repo"].find_by_bot_id("B001"))


@when("我以 worker id 查詢單一 worker")
def query_by_id(context):
    context["by_id"] = _run(context["repo"].find_by_id("some-worker-id"))


@then("Worker DB 只應被查詢一次")
def db_once(context):
    assert context["inner"].find_by_bot_id.await_count == 1


@then("兩次查詢結果應相同")
def results_equal(context):
    assert context["first"] == context["second"]
    assert len(context["first"]) == 2


@then("Worker DB 應被查詢兩次")
def db_twice(context):
    assert context["inner"].find_by_bot_id.await_count == 2


@then("再次查詢應重新查詢 Worker DB")
def requery_hits_db(context):
    # 快取後 1 次 + 失效後重查 1 次 = 2
    assert context["inner"].find_by_bot_id.await_count == 2


@then("應直接委派內層 repository")
def find_by_id_delegated(context):
    context["inner"].find_by_id.assert_awaited_once_with("some-worker-id")
