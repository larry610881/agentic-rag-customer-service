"""Request-scoped trace logging — configurable via TRACE_THRESHOLD_MS.

- TRACE_THRESHOLD_MS=0    → 停用（預設）：不印 console、request_logs.trace_steps 不寫
- TRACE_THRESHOLD_MS=2000 → 只有耗時 >= 2000ms 的請求才印 console 並持久化 trace_steps

Issue #59：原本門檻只控 console、DB 一律寫入，導致每個請求把全部 SQL 片段塞進
request_logs。現在門檻同時決定 console 與持久化。
"""

import time
from contextlib import contextmanager
from contextvars import ContextVar

import structlog

_logger = structlog.get_logger("trace")

_trace_buffer: ContextVar[list[dict] | None] = ContextVar(
    "_trace_buffer", default=None
)


def _get_threshold_ms() -> int:
    from src.config import settings

    return settings.trace_threshold_ms


def init_trace() -> None:
    """Call at request start to begin buffering trace entries."""
    _trace_buffer.set([])


def _record(step: str, elapsed_ms: float, **extra: object) -> None:
    buf = _trace_buffer.get()
    if buf is not None:
        buf.append({"step": step, "elapsed_ms": elapsed_ms, **extra})


@contextmanager
def trace_step(name: str):
    """Buffer elapsed time for a named step."""
    t0 = time.perf_counter()
    yield
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    _record(name, elapsed_ms)


def record_sql(elapsed_ms: float, sql: str) -> None:
    """Buffer a SQL query timing entry (called from engine events)."""
    _record("sql", elapsed_ms, sql=sql)


def flush_trace(request_elapsed_ms: float) -> list[dict] | None:
    """Flush buffered entries. Returns them only when the request crossed the
    threshold (threshold 0 = disabled) — the return value is what gets persisted."""
    buf = _trace_buffer.get()
    _trace_buffer.set(None)
    if not buf:
        return None

    threshold = _get_threshold_ms()
    if threshold <= 0 or request_elapsed_ms < threshold:
        return None

    for entry in buf:
        _logger.info("trace.step", **entry)
    _logger.info(
        "trace.summary",
        total_steps=len(buf),
        request_elapsed_ms=round(request_elapsed_ms, 1),
    )
    return buf
