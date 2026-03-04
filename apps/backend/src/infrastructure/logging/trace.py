"""Lightweight request-scoped trace logging for performance diagnostics.

Usage:
    from src.infrastructure.logging.trace import trace_step

    with trace_step("find_by_name"):
        tenant = await tenant_repo.find_by_name(name)
    # logs: trace.step  step=find_by_name  elapsed_ms=152.3
"""

import time
from contextlib import contextmanager

import structlog

_logger = structlog.get_logger("trace")


@contextmanager
def trace_step(name: str):
    """Log elapsed time for a named step. Works with sync and async code."""
    t0 = time.perf_counter()
    yield
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    _logger.info("trace.step", step=name, elapsed_ms=elapsed_ms)
