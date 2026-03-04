"""Request-scoped trace logging — configurable via TRACE_THRESHOLD_MS.

- TRACE_THRESHOLD_MS=0  → always flush (log every request)
- TRACE_THRESHOLD_MS=2000 → only flush when request >= 2000ms
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
    """Log buffered entries (console controlled by threshold) and return them."""
    buf = _trace_buffer.get()
    _trace_buffer.set(None)
    if not buf:
        return None

    # Console output still respects threshold
    threshold = _get_threshold_ms()
    if threshold == 0 or request_elapsed_ms >= threshold:
        for entry in buf:
            _logger.info("trace.step", **entry)
        _logger.info(
            "trace.summary",
            total_steps=len(buf),
            request_elapsed_ms=round(request_elapsed_ms, 1),
        )

    return buf
