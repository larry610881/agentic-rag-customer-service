"""Error Event API — public report + admin management."""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.application.observability.error_event_use_cases import (
    GetErrorEventUseCase,
    ListErrorEventsUseCase,
    ReportErrorCommand,
    ReportErrorUseCase,
    ResolveErrorEventUseCase,
)
from src.container import Container
from src.interfaces.api.deps import require_role

router = APIRouter(tags=["error-events"])


# --- Public endpoint (rate-limited at middleware level) ---


class _ReportErrorBody(BaseModel):
    source: str
    error_type: str
    message: str
    stack_trace: str | None = None
    path: str | None = None
    method: str | None = None
    status_code: int | None = None
    user_agent: str | None = None
    extra: dict | None = None


@router.post("/api/v1/error-events", status_code=201)
@inject
async def report_error(
    body: _ReportErrorBody,
    use_case: ReportErrorUseCase = Depends(
        Provide[Container.report_error_use_case]
    ),
):
    event = await use_case.execute(
        ReportErrorCommand(
            source=body.source,
            error_type=body.error_type,
            message=body.message,
            stack_trace=body.stack_trace,
            path=body.path,
            method=body.method,
            status_code=body.status_code,
            user_agent=body.user_agent,
            extra=body.extra,
        )
    )
    return {"id": event.id, "fingerprint": event.fingerprint}


# --- Admin endpoints ---


@router.get("/api/v1/admin/error-events")
@inject
async def list_error_events(
    _: object = Depends(require_role("system_admin")),
    source: str | None = Query(default=None),
    resolved: bool | None = Query(default=None),
    fingerprint: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    use_case: ListErrorEventsUseCase = Depends(
        Provide[Container.list_error_events_use_case]
    ),
):
    items, total = await use_case.execute(
        source=source,
        resolved=resolved,
        fingerprint=fingerprint,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "fingerprint": e.fingerprint,
                "source": e.source,
                "error_type": e.error_type,
                "message": e.message,
                "path": e.path,
                "method": e.method,
                "status_code": e.status_code,
                "tenant_id": e.tenant_id,
                "resolved": e.resolved,
                "resolved_at": (
                    e.resolved_at.isoformat() if e.resolved_at else None
                ),
                "resolved_by": e.resolved_by,
                "created_at": (
                    e.created_at.isoformat() if e.created_at else None
                ),
            }
            for e in items
        ],
    }


@router.get("/api/v1/admin/error-events/{event_id}")
@inject
async def get_error_event(
    event_id: str,
    _: object = Depends(require_role("system_admin")),
    use_case: GetErrorEventUseCase = Depends(
        Provide[Container.get_error_event_use_case]
    ),
):
    e = await use_case.execute(event_id)
    return {
        "id": e.id,
        "fingerprint": e.fingerprint,
        "source": e.source,
        "error_type": e.error_type,
        "message": e.message,
        "stack_trace": e.stack_trace,
        "request_id": e.request_id,
        "path": e.path,
        "method": e.method,
        "status_code": e.status_code,
        "tenant_id": e.tenant_id,
        "user_agent": e.user_agent,
        "extra": e.extra,
        "resolved": e.resolved,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "resolved_by": e.resolved_by,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.patch("/api/v1/admin/error-events/{event_id}/resolve")
@inject
async def resolve_error_event(
    event_id: str,
    tenant: object = Depends(require_role("system_admin")),
    use_case: ResolveErrorEventUseCase = Depends(
        Provide[Container.resolve_error_event_use_case]
    ),
):
    resolved_by = getattr(tenant, "user_id", "system")
    e = await use_case.execute(event_id, resolved_by)
    return {
        "id": e.id,
        "resolved": e.resolved,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "resolved_by": e.resolved_by,
    }
