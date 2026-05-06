"""Admin Outbox Router — Phase E

DLQ 視覺化 + retry / abandon。只 system_admin 可用（outbox 是跨租戶基建）。

Endpoints
- GET    /api/v1/admin/outbox/dead-letter           List DLQ
- POST   /api/v1/admin/outbox/dead-letter/{id}/retry Single requeue
- POST   /api/v1/admin/outbox/dead-letter/bulk-retry Bulk requeue (by filter)
- DELETE /api/v1/admin/outbox/dead-letter/{id}      Hard-delete (abandon)
- GET    /api/v1/admin/outbox/stats                  Dashboard stats
"""

from __future__ import annotations

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.application.outbox.admin_use_cases import (
    AbandonOutboxEventCommand,
    AbandonOutboxEventUseCase,
    BulkRequeueDeadLetterCommand,
    BulkRequeueDeadLetterUseCase,
    GetOutboxStatsUseCase,
    ListDeadLetterQuery,
    ListDeadLetterUseCase,
    RequeueOutboxEventCommand,
    RequeueOutboxEventUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, require_role

router = APIRouter(prefix="/api/v1/admin/outbox", tags=["admin-outbox"])


# ── Schemas ───────────────────────────────────────────────────────


class OutboxEventResponse(BaseModel):
    id: str
    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    next_attempt_at: str
    created_at: str
    completed_at: str | None
    age_seconds: float


class OutboxStatsResponse(BaseModel):
    pending_count: int
    in_progress_count: int
    done_count: int
    dead_count: int
    oldest_pending_age_seconds: float | None


class BulkRequeueRequest(BaseModel):
    event_type: str | None = None
    tenant_id: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class BulkRequeueResponse(BaseModel):
    requeued_count: int
    event_ids: list[str]


class AbandonRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


def _to_response(event) -> OutboxEventResponse:
    from datetime import datetime, timezone
    age = (datetime.now(timezone.utc) - event.created_at).total_seconds()
    return OutboxEventResponse(
        id=event.id,
        tenant_id=event.tenant_id,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        payload=event.payload,
        status=event.status,
        attempts=event.attempts,
        max_attempts=event.max_attempts,
        last_error=event.last_error,
        next_attempt_at=event.next_attempt_at.isoformat(),
        created_at=event.created_at.isoformat(),
        completed_at=event.completed_at.isoformat() if event.completed_at
        else None,
        age_seconds=max(0.0, age),
    )


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/dead-letter", response_model=list[OutboxEventResponse])
@inject
async def list_dead_letter(
    event_type: str | None = Query(None),
    tenant_id_filter: str | None = Query(None, alias="tenant_id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListDeadLetterUseCase = Depends(
        Provide[Container.list_dead_letter_outbox_use_case]
    ),
) -> list[OutboxEventResponse]:
    events = await use_case.execute(
        ListDeadLetterQuery(
            event_type=event_type,
            tenant_id=tenant_id_filter,
            limit=limit,
            offset=offset,
        )
    )
    return [_to_response(e) for e in events]


@router.get("/stats", response_model=OutboxStatsResponse)
@inject
async def get_stats(
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetOutboxStatsUseCase = Depends(
        Provide[Container.get_outbox_stats_use_case]
    ),
) -> OutboxStatsResponse:
    stats = await use_case.execute()
    return OutboxStatsResponse(
        pending_count=stats.pending_count,
        in_progress_count=stats.in_progress_count,
        done_count=stats.done_count,
        dead_count=stats.dead_count,
        oldest_pending_age_seconds=stats.oldest_pending_age_seconds,
    )


@router.post(
    "/dead-letter/{event_id}/retry",
    response_model=OutboxEventResponse,
)
@inject
async def retry_event(
    event_id: str,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: RequeueOutboxEventUseCase = Depends(
        Provide[Container.requeue_outbox_event_use_case]
    ),
) -> OutboxEventResponse:
    try:
        event = await use_case.execute(
            RequeueOutboxEventCommand(
                event_id=event_id,
                actor=admin.user_id or admin.tenant_id or "",
            )
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return _to_response(event)


@router.post(
    "/dead-letter/bulk-retry",
    response_model=BulkRequeueResponse,
)
@inject
async def bulk_retry(
    body: BulkRequeueRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: BulkRequeueDeadLetterUseCase = Depends(
        Provide[Container.bulk_requeue_dead_letter_use_case]
    ),
) -> BulkRequeueResponse:
    result = await use_case.execute(
        BulkRequeueDeadLetterCommand(
            event_type=body.event_type,
            tenant_id=body.tenant_id,
            limit=body.limit,
            actor=admin.user_id or admin.tenant_id or "",
        )
    )
    return BulkRequeueResponse(
        requeued_count=result.requeued_count,
        event_ids=result.event_ids,
    )


@router.delete(
    "/dead-letter/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def abandon_event(
    event_id: str,
    body: AbandonRequest | None = None,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: AbandonOutboxEventUseCase = Depends(
        Provide[Container.abandon_outbox_event_use_case]
    ),
) -> None:
    try:
        await use_case.execute(
            AbandonOutboxEventCommand(
                event_id=event_id,
                actor=admin.user_id or admin.tenant_id or "",
                reason=(body.reason if body else "") or "",
            )
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
