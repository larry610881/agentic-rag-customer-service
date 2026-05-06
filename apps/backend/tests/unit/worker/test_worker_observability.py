"""Layer 5 — worker structured-log observability shape.

Layer 1 wrapper 已經在 emit ``worker.job.start`` / ``.complete`` /
``.retry`` / ``.permanent_fail`` / ``.exhausted``，本檔驗 schema 不漏欄位
（GCP log-based metric / alert 所需的關鍵 key）。
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.worker_resilience import execute_with_resilience


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_success_emits_start_and_complete_with_latency_ms():
    async def _ok() -> str:
        await asyncio.sleep(0)  # let event loop tick so latency_ms ≥ 0
        return "ok"

    with structlog.testing.capture_logs() as logs:
        result = _run(execute_with_resilience(
            ctx={"job_try": 1},
            task_name="process_document",
            task_id="task-001",
            coro_factory=_ok,
            container_factory=lambda: _NoopContainer(),
            extra_log={"document_id": "doc-001"},
        ))

    assert result == "ok"

    starts = [e for e in logs if e["event"] == "worker.job.start"]
    completes = [e for e in logs if e["event"] == "worker.job.complete"]
    assert len(starts) == 1
    assert len(completes) == 1

    s = starts[0]
    assert s["job"] == "process_document"
    assert s["task_id"] == "task-001"
    assert s["attempt"] == 1
    assert s["document_id"] == "doc-001"

    c = completes[0]
    assert c["job"] == "process_document"
    assert c["status"] == "ok"
    assert c["attempt"] == 1
    # latency_ms 必須是非負整數，alert 才能設 percentile / threshold
    assert isinstance(c["latency_ms"], int)
    assert c["latency_ms"] >= 0
    assert c["document_id"] == "doc-001"


def test_retry_event_carries_defer_seconds_and_next_attempt():
    from pymilvus.exceptions import MilvusException

    async def _transient() -> Any:
        raise MilvusException(message="Fail connecting to server")

    with structlog.testing.capture_logs() as logs:
        try:
            _run(execute_with_resilience(
                ctx={"job_try": 1},
                task_name="process_document",
                task_id="task-002",
                coro_factory=_transient,
                container_factory=lambda: _NoopContainer(),
            ))
        except BaseException:
            pass  # Retry raises; that's expected

    retries = [e for e in logs if e["event"] == "worker.job.retry"]
    assert len(retries) == 1
    r = retries[0]
    assert r["job"] == "process_document"
    assert r["attempt"] == 1
    assert r["next_attempt"] == 2
    assert r["defer_seconds"] == 5
    assert r["error"] == "MilvusException"


def test_permanent_fail_event_emitted_for_value_error():
    async def _bad() -> Any:
        raise ValueError("API key is empty")

    with structlog.testing.capture_logs() as logs:
        _run(execute_with_resilience(
            ctx={"job_try": 1},
            task_name="extract_memory",
            task_id="profile-007",
            coro_factory=_bad,
            container_factory=lambda: _NoopContainer(),
        ))

    fails = [e for e in logs if e["event"] == "worker.job.permanent_fail"]
    assert len(fails) == 1
    f = fails[0]
    assert f["job"] == "extract_memory"
    assert f["task_id"] == "profile-007"
    assert f["error"] == "ValueError"
    assert isinstance(f["latency_ms"], int)


def test_exhausted_event_emitted_at_last_attempt():
    from pymilvus.exceptions import MilvusException

    async def _transient() -> Any:
        raise MilvusException(message="connection refused")

    with structlog.testing.capture_logs() as logs:
        try:
            _run(execute_with_resilience(
                ctx={"job_try": 3},
                task_name="classify_kb",
                task_id="kb-x",
                coro_factory=_transient,
                container_factory=lambda: _NoopContainer(),
            ))
        except BaseException:
            pass

    exhausted = [e for e in logs if e["event"] == "worker.job.exhausted"]
    assert len(exhausted) == 1
    assert exhausted[0]["attempt"] == 3
    assert exhausted[0]["error"] == "MilvusException"


# ── helpers ─────────────────────────────────────────────────


class _NoopRepo:
    async def update_status(self, **_kwargs: Any) -> None:
        return None


class _NoopContainer:
    def processing_task_repository(self) -> _NoopRepo:
        return _NoopRepo()
