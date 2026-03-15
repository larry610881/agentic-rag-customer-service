"""Fire-and-forget writer for error events."""

import uuid
from datetime import datetime, timezone

import structlog

from src.domain.observability.error_event import ErrorEvent, compute_fingerprint
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.models.error_event_model import ErrorEventModel
from src.infrastructure.notification.dispatch_helper import (
    dispatch_error_notification,
)

_logger = structlog.get_logger("error_event_writer")


async def write_error_event(
    error_detail: str,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    tenant_id: str | None = None,
) -> None:
    """Write a backend error event. Swallows all errors."""
    try:
        parts = error_detail.split(": ", 1)
        error_type = parts[0] if parts else "UnknownError"
        message = parts[1] if len(parts) > 1 else error_detail
        fp = compute_fingerprint("backend", error_type, path)

        async with async_session_factory() as session:
            row = ErrorEventModel(
                id=uuid.uuid4().hex,
                fingerprint=fp,
                source="backend",
                error_type=error_type,
                message=message,
                request_id=request_id,
                path=path,
                method=method,
                status_code=status_code,
                tenant_id=tenant_id,
                resolved=False,
                created_at=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()

        # Fire-and-forget notification dispatch
        event = ErrorEvent(
            id=row.id,
            fingerprint=fp,
            source="backend",
            error_type=error_type,
            message=message,
            request_id=request_id,
            path=path,
            method=method,
            status_code=status_code,
            tenant_id=tenant_id,
        )
        await dispatch_error_notification(event)
    except Exception:
        _logger.warning("error_event_write_failed", exc_info=True)
