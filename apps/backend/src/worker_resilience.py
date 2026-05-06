"""arq Worker resilience — transient/permanent classification + Retry policy.

Layer 1 of the worker resilience stack. Each arq task wraps its body with
``execute_with_resilience(...)``; the wrapper:

* classifies the exception (transient → retry / permanent → mark failed);
* on transient + remaining attempts: raises ``arq.jobs.Retry(defer=N)`` with
  exponential backoff (5s → 30s → 2min);
* on permanent or exhausted retries: writes ``processing_task.status='failed'``
  + ``error_message`` for admin UI / DLQ visibility, then either swallows
  (permanent) or re-raises (exhausted) so arq stops retrying;
* emits structured logs (``worker.job.start`` / ``.complete`` / ``.retry`` /
  ``.permanent_fail`` / ``.exhausted``) for GCP log-based metrics.

Triggered by 5/6 carrefour DM reprocess pages 50/54/55 transient failures
that required manual user intervention.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from arq import Retry
from sqlalchemy.exc import OperationalError as SAOperationalError
from sqlalchemy.exc import TimeoutError as SATimeoutError

try:
    from pymilvus.exceptions import MilvusException
except ImportError:  # pragma: no cover — pymilvus always installed in prod
    class MilvusException(Exception):  # type: ignore[no-redef]
        pass

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

MAX_TRIES: int = 3
BACKOFFS: tuple[int, ...] = (5, 30, 120)

# 4xx that retrying cannot fix: auth / authz / not-found / unprocessable.
PERMANENT_HTTP_STATUS = frozenset({401, 403, 404, 422})


def is_permanent(exc: BaseException) -> bool:
    """設定 / 資料錯誤 — retry 沒用，直接落 DLQ。"""
    if isinstance(exc, ValueError | KeyError | FileNotFoundError | TypeError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", 0) if response is not None else 0
        return status in PERMANENT_HTTP_STATUS
    return False


def is_transient(exc: BaseException) -> bool:
    """網路 / DB / 向量庫短暫故障 — 重試可能恢復。"""
    if isinstance(exc, asyncio.TimeoutError | TimeoutError):
        return True
    if isinstance(
        exc,
        httpx.ConnectError
        | httpx.ReadTimeout
        | httpx.WriteTimeout
        | httpx.RemoteProtocolError
        | httpx.PoolTimeout,
    ):
        return True
    if isinstance(exc, SATimeoutError | SAOperationalError):
        return True
    if isinstance(exc, MilvusException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", 0) if response is not None else 0
        return status >= 500 or status == 429
    return False


async def _mark_task_dead(
    task_id: str,
    exc: BaseException,
    attempt: int,
    container_factory: Callable[[], Any] | None,
) -> None:
    """把 processing_task 標 failed + error_message。

    無 task_id 對應的 row 時 SQL UPDATE 是 no-op（例如 run_evaluation 用
    trace_id），符合預期，不需特別處理。
    """
    if not task_id:
        return
    try:
        if container_factory is None:
            from src.container import Container
            container = Container()
        else:
            container = container_factory()
        repo = container.processing_task_repository()
        msg = (
            f"[attempt={attempt}] {type(exc).__name__}: "
            f"{str(exc)[:500]}"
        )
        await repo.update_status(
            task_id=task_id,
            status="failed",
            error_message=msg,
        )
    except Exception:
        logger.warning(
            "worker.mark_dead.failed",
            task_id=task_id,
            attempt=attempt,
            exc_info=True,
        )


async def execute_with_resilience(
    *,
    ctx: dict[str, Any],
    task_name: str,
    task_id: str,
    coro_factory: Callable[[], Awaitable[Any]],
    container_factory: Callable[[], Any] | None = None,
    extra_log: dict[str, Any] | None = None,
) -> Any:
    """Wrap arq job body with retry + DLQ classification.

    Args:
        ctx: arq job context (provides ``job_try``).
        task_name: short name (``process_document``, ``classify_kb`` …).
        task_id: ``processing_task.id`` (or trace-like id for jobs without one).
        coro_factory: nullary callable that builds the job's awaitable. We
            invoke it inside the try-block so that container creation /
            session resolution failures are also classified.
        container_factory: optional override for testing; prod uses
            ``src.container.Container``.
        extra_log: extra structured-log fields (e.g. ``document_id``).

    Returns:
        The coroutine's result on success; ``None`` after a permanent failure
        (so arq does not record a retry).

    Raises:
        ``arq.jobs.Retry``: on transient failure with retries remaining.
        Original exception: on transient failure with retries exhausted.
    """
    job_try = int(ctx.get("job_try", 1))
    extra = dict(extra_log or {})
    started = time.monotonic()

    logger.info(
        "worker.job.start",
        job=task_name,
        task_id=task_id,
        attempt=job_try,
        **extra,
    )

    try:
        result = await coro_factory()
    except Retry:
        # Pass-through: nested code may already raise Retry intentionally.
        raise
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)

        if is_permanent(exc):
            logger.error(
                "worker.job.permanent_fail",
                job=task_name,
                task_id=task_id,
                attempt=job_try,
                latency_ms=latency_ms,
                error=type(exc).__name__,
                error_msg=str(exc)[:300],
                **extra,
            )
            await _mark_task_dead(
                task_id, exc, job_try, container_factory,
            )
            return None  # arq sees success → no retry on permanent.

        transient = is_transient(exc)
        if not transient:
            logger.warning(
                "worker.job.unknown_exc_treated_as_transient",
                job=task_name,
                task_id=task_id,
                attempt=job_try,
                error=type(exc).__name__,
                error_msg=str(exc)[:300],
                **extra,
            )

        if job_try >= MAX_TRIES:
            logger.error(
                "worker.job.exhausted",
                job=task_name,
                task_id=task_id,
                attempt=job_try,
                latency_ms=latency_ms,
                error=type(exc).__name__,
                error_msg=str(exc)[:300],
                **extra,
            )
            await _mark_task_dead(
                task_id, exc, job_try, container_factory,
            )
            raise

        defer = BACKOFFS[job_try - 1] if job_try - 1 < len(BACKOFFS) else BACKOFFS[-1]
        logger.warning(
            "worker.job.retry",
            job=task_name,
            task_id=task_id,
            attempt=job_try,
            next_attempt=job_try + 1,
            defer_seconds=defer,
            error=type(exc).__name__,
            error_msg=str(exc)[:300],
            latency_ms=latency_ms,
            **extra,
        )
        raise Retry(defer=defer) from exc

    latency_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "worker.job.complete",
        job=task_name,
        task_id=task_id,
        status="ok",
        attempt=job_try,
        latency_ms=latency_ms,
        **extra,
    )
    return result
