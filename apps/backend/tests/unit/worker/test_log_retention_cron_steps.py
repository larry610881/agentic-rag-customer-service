"""Log 保留政策排程 BDD Step Definitions（Issue #59）"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src import worker as worker_mod
from src.domain.observability.log_retention_policy import (
    LogRetentionPolicy,
    should_run_cleanup,
)

scenarios("unit/worker/log_retention_cron.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _at(hour: int) -> datetime:
    return datetime(2026, 9, 2, hour, 5, tzinfo=timezone.utc)


@when("讀取 worker 的 cron 清單")
def read_cron(context):
    context["cron"] = [
        c.coroutine.__name__ for c in worker_mod.WorkerSettings.cron_jobs
    ]


@then(parsers.parse('cron 清單應包含 "{name}"'))
def cron_includes(context, name):
    assert name in context["cron"], context["cron"]


@given(parsers.parse(
    "保留政策 enabled={enabled} cleanup_hour={hour:d} "
    "interval={interval:d} 上次執行={last}"
))
def policy(context, enabled, hour, interval, last):
    last_at = None
    if last == "30min":
        last_at = _at(hour) - timedelta(minutes=30)
    context["policy"] = LogRetentionPolicy(
        enabled=(enabled == "true"),
        cleanup_hour=hour,
        cleanup_interval_hours=interval,
        last_cleanup_at=last_at,
    )


@when(parsers.parse("於 UTC {hour:d} 點判斷是否執行"))
def decide(context, hour):
    context["decision"] = should_run_cleanup(context["policy"], _at(hour))


@then(parsers.parse("判斷結果應為 {expected}"))
def decision_is(context, expected):
    assert context["decision"] is (expected == "true")


def _patch_container(monkeypatch, context):
    get_uc = MagicMock()
    get_uc.execute = AsyncMock(return_value=context["policy"])
    cleanup_uc = MagicMock()
    cleanup_uc.execute = AsyncMock(return_value=7)
    container = MagicMock()
    container.get_log_retention_policy_use_case.return_value = get_uc
    container.execute_log_cleanup_use_case.return_value = cleanup_uc
    monkeypatch.setattr(worker_mod, "_new_container", lambda: container)
    context["cleanup_uc"] = cleanup_uc


@when(parsers.parse("worker 於 UTC {hour:d} 點執行 log_retention_cleanup_task"))
def run_task(context, monkeypatch, hour):
    _patch_container(monkeypatch, context)
    _run(worker_mod.log_retention_cleanup_task({}, now=_at(hour)))


@then("應呼叫 ExecuteLogCleanupUseCase")
def cleanup_called(context):
    context["cleanup_uc"].execute.assert_awaited_once()


@then("不應呼叫 ExecuteLogCleanupUseCase")
def cleanup_not_called(context):
    context["cleanup_uc"].execute.assert_not_awaited()
