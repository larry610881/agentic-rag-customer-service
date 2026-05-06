"""Worker resilience BDD step definitions（Layer 1）."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from arq import Retry
from pymilvus.exceptions import MilvusException
from pytest_bdd import given, parsers, scenarios, then, when

from src.worker_resilience import execute_with_resilience

scenarios("unit/worker/worker_resilience.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Fakes ─────────────────────────────────────────────────────────


class _FakeProcessingTaskRepo:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    async def update_status(
        self,
        task_id: str,
        status: str,
        progress: int | None = None,
        error_message: str | None = None,
    ) -> None:
        self.updates.append(
            {
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "error_message": error_message,
            }
        )


class _FakeContainer:
    def __init__(self, repo: _FakeProcessingTaskRepo) -> None:
        self._repo = repo

    def processing_task_repository(self) -> _FakeProcessingTaskRepo:
        return self._repo


def _make_http_error(status_code: int) -> httpx.HTTPStatusError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=MagicMock(spec=httpx.Request),
        response=response,
    )


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def context() -> dict:
    repo = _FakeProcessingTaskRepo()
    return {
        "ctx": {"job_try": 1},
        "fake_repo": repo,
        "container_factory": lambda: _FakeContainer(repo),
        "task_id": "task-test-001",
        "raised": None,
        "result": None,
    }


# ── Given ─────────────────────────────────────────────────────────


@given(parsers.parse("worker 的 job_try 為 {job_try:d}"))
def set_job_try(context: dict, job_try: int) -> None:
    context["ctx"]["job_try"] = job_try


@given("內層業務拋 MilvusException 連線失敗")
def inner_raises_milvus(context: dict) -> None:
    async def _coro() -> Any:
        raise MilvusException(message="Fail connecting to server")

    context["coro_factory"] = _coro


@given("內層業務拋 ValueError 空 API key")
def inner_raises_value_error(context: dict) -> None:
    async def _coro() -> Any:
        raise ValueError("API key is empty")

    context["coro_factory"] = _coro


@given(parsers.parse('內層業務回傳 "{value}"'))
def inner_returns(context: dict, value: str) -> None:
    async def _coro() -> Any:
        return value

    context["coro_factory"] = _coro


@given(parsers.parse('內層業務拋 httpx.HTTPStatusError 狀態碼 {status:d}'))
def inner_raises_http(context: dict, status: int) -> None:
    err = _make_http_error(status)

    async def _coro() -> Any:
        raise err

    context["coro_factory"] = _coro


# ── When ──────────────────────────────────────────────────────────


@when("執行包了 resilience wrapper 的任務")
def run_resilience(context: dict) -> None:
    try:
        context["result"] = _run(
            execute_with_resilience(
                ctx=context["ctx"],
                task_name="test_task",
                task_id=context["task_id"],
                coro_factory=context["coro_factory"],
                container_factory=context["container_factory"],
            )
        )
    except BaseException as exc:  # noqa: BLE001 — 測試需捕捉 Retry
        context["raised"] = exc


# ── Then ──────────────────────────────────────────────────────────


@then(parsers.parse("應該 raise arq.Retry，defer 為 {defer:d} 秒"))
def assert_retry(context: dict, defer: int) -> None:
    raised = context["raised"]
    assert isinstance(raised, Retry), f"expected Retry, got {raised!r}"
    # arq.Retry stores defer as ms internally (to_ms(seconds))
    assert raised.defer_score == defer * 1000, (
        f"defer mismatch: {raised.defer_score}ms != {defer * 1000}ms"
    )


@then("processing_task 不應被標記為 failed")
def assert_repo_not_marked(context: dict) -> None:
    repo: _FakeProcessingTaskRepo = context["fake_repo"]
    failed = [u for u in repo.updates if u["status"] == "failed"]
    assert not failed, f"unexpected failed updates: {failed}"


@then("不應拋出例外給 arq")
def assert_no_raise(context: dict) -> None:
    assert context["raised"] is None, (
        f"unexpected exception raised: {context['raised']!r}"
    )


@then("processing_task 應被標 status=failed")
def assert_repo_failed(context: dict) -> None:
    repo: _FakeProcessingTaskRepo = context["fake_repo"]
    failed = [u for u in repo.updates if u["status"] == "failed"]
    assert len(failed) == 1, f"expected 1 failed update, got {failed}"
    assert failed[0]["task_id"] == context["task_id"]


@then(parsers.parse('processing_task error_message 應包含 "{needle}"'))
def assert_error_message_contains(context: dict, needle: str) -> None:
    repo: _FakeProcessingTaskRepo = context["fake_repo"]
    failed = [u for u in repo.updates if u["status"] == "failed"]
    assert failed, "no failed update recorded"
    assert needle in (failed[0]["error_message"] or ""), (
        f"error_message {failed[0]['error_message']!r} does not contain {needle!r}"
    )


@then("應拋出原始 MilvusException")
def assert_raises_milvus(context: dict) -> None:
    raised = context["raised"]
    assert isinstance(raised, MilvusException), (
        f"expected MilvusException, got {raised!r}"
    )


@then(parsers.parse('應拿到 "{value}" 結果'))
def assert_result(context: dict, value: str) -> None:
    assert context["result"] == value, (
        f"result mismatch: {context['result']!r} != {value!r}"
    )
