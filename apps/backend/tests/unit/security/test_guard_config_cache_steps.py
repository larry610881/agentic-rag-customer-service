"""Guard 設定快取 BDD Steps — Issue #52 E2"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.security.guard_config import GuardRulesConfig
from src.infrastructure.db.repositories.cached_guard_rules_config_repository import (
    CachedGuardRulesConfigRepository,
    invalidate_guard_rules_cache,
)

scenarios("unit/security/guard_config_cache.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _reset_cache():
    invalidate_guard_rules_cache()
    yield
    invalidate_guard_rules_cache()


@pytest.fixture
def context():
    return {}


def _make_repo(config):
    inner = AsyncMock()
    inner.get = AsyncMock(return_value=config)
    inner.save = AsyncMock()
    return CachedGuardRulesConfigRepository(inner=inner), inner


@given("Guard 設定存在於 DB")
def config_in_db(context):
    config = GuardRulesConfig(llm_input_guard_enabled=True)
    repo, inner = _make_repo(config)
    context.update(repo=repo, inner=inner, config=config)


@given("DB 中沒有 Guard 設定")
def no_config_in_db(context):
    repo, inner = _make_repo(None)
    context.update(repo=repo, inner=inner)


@given("Guard 設定存在於 DB 且已被快取")
def config_cached(context):
    config_in_db(context)
    _run(context["repo"].get())
    assert context["inner"].get.await_count == 1


@when("我連續讀取 Guard 設定兩次")
def read_twice(context):
    context["first"] = _run(context["repo"].get())
    context["second"] = _run(context["repo"].get())


@when("我儲存新的 Guard 設定後再次讀取")
def save_then_read(context):
    new_config = GuardRulesConfig(llm_guard_model="openai:gpt-5-nano")
    _run(context["repo"].save(new_config))
    context["inner"].get = AsyncMock(return_value=new_config)
    context["after_save"] = _run(context["repo"].get())


@then("DB 只應被查詢一次")
def db_queried_once(context):
    assert context["inner"].get.await_count == 1


@then("兩次讀取結果應相同")
def results_equal(context):
    assert context["first"] is context["second"]
    assert context["first"] == context["config"]


@then("讀取結果應為 None")
def result_is_none(context):
    assert context["first"] is None
    assert context["second"] is None


@then("儲存應委派內層 repository")
def save_delegated(context):
    context["inner"].save.assert_awaited_once()


@then("再次讀取應重新查詢 DB")
def reread_hits_db(context):
    assert context["inner"].get.await_count == 1  # 換過的新 mock 被打了一次
    assert context["after_save"].llm_guard_model == "openai:gpt-5-nano"
