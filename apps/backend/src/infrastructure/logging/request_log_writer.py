"""Fire-and-forget writer that persists request trace data to the DB."""

import uuid

import structlog

from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.models.request_log_model import RequestLogModel

_logger = structlog.get_logger("request_log_writer")


async def write_request_log(
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    elapsed_ms: float,
    trace_steps: list[dict] | None,
) -> None:
    """Persist a single request log entry. Swallows all errors."""
    try:
        async with async_session_factory() as session:
            row = RequestLogModel(
                id=uuid.uuid4().hex,
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                elapsed_ms=round(elapsed_ms, 1),
                trace_steps=trace_steps,
            )
            session.add(row)
            await session.commit()
    except Exception:
        _logger.warning("request_log_write_failed", exc_info=True)
