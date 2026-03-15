"""Error Event Use Cases — report, list, get, resolve."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.observability.error_event import (
    ErrorEvent,
    ErrorEventRepository,
    compute_fingerprint,
)
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class ReportErrorCommand:
    source: str
    error_type: str
    message: str
    stack_trace: str | None = None
    request_id: str | None = None
    path: str | None = None
    method: str | None = None
    status_code: int | None = None
    tenant_id: str | None = None
    user_agent: str | None = None
    extra: dict | None = None


class ReportErrorUseCase:
    def __init__(self, error_event_repo: ErrorEventRepository) -> None:
        self._repo = error_event_repo

    async def execute(self, command: ReportErrorCommand) -> ErrorEvent:
        fp = compute_fingerprint(command.source, command.error_type, command.path)
        event = ErrorEvent(
            id=uuid.uuid4().hex,
            fingerprint=fp,
            source=command.source,
            error_type=command.error_type,
            message=command.message,
            stack_trace=command.stack_trace,
            request_id=command.request_id,
            path=command.path,
            method=command.method,
            status_code=command.status_code,
            tenant_id=command.tenant_id,
            user_agent=command.user_agent,
            extra=command.extra,
            resolved=False,
            created_at=datetime.now(timezone.utc),
        )
        return await self._repo.save(event)


class ListErrorEventsUseCase:
    def __init__(self, error_event_repo: ErrorEventRepository) -> None:
        self._repo = error_event_repo

    async def execute(
        self,
        *,
        source: str | None = None,
        resolved: bool | None = None,
        fingerprint: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ErrorEvent], int]:
        return await self._repo.list_events(
            source=source,
            resolved=resolved,
            fingerprint=fingerprint,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )


class GetErrorEventUseCase:
    def __init__(self, error_event_repo: ErrorEventRepository) -> None:
        self._repo = error_event_repo

    async def execute(self, event_id: str) -> ErrorEvent:
        event = await self._repo.get_by_id(event_id)
        if event is None:
            raise EntityNotFoundError("ErrorEvent", event_id)
        return event


class ResolveErrorEventUseCase:
    def __init__(self, error_event_repo: ErrorEventRepository) -> None:
        self._repo = error_event_repo

    async def execute(self, event_id: str, resolved_by: str) -> ErrorEvent:
        event = await self._repo.resolve(event_id, resolved_by)
        if event is None:
            raise EntityNotFoundError("ErrorEvent", event_id)
        return event
