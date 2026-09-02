"""對話摘要排程條件 BDD Step Definitions（Issue #59）"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src import worker as worker_mod

scenarios("unit/worker/conversation_summary_policy.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given(parsers.parse("設定 conversation_summary_min_messages 為 {n:d}"))
def set_min_messages(context, monkeypatch, n):
    conv_repo = MagicMock()
    conv_repo.find_pending_summary = AsyncMock(return_value=[])
    container = MagicMock()
    container.conversation_repository.return_value = conv_repo
    container.config.return_value = MagicMock(conversation_summary_min_messages=n)
    monkeypatch.setattr(worker_mod, "_new_container", lambda: container)
    context["conv_repo"] = conv_repo


@when("worker 執行 conversation_summary_scan_task")
def run_scan(context):
    _run(worker_mod.conversation_summary_scan_task({"redis": AsyncMock()}))


@then(parsers.parse("find_pending_summary 應以 min_message_count={n:d} 被呼叫"))
def scan_kwargs(context, n):
    kwargs = context["conv_repo"].find_pending_summary.call_args.kwargs
    assert kwargs.get("min_message_count") == n, kwargs
