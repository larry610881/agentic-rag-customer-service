"""Prompt optimizer runs API endpoints."""

from __future__ import annotations

import logging
from math import ceil
from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.eval_dataset.run_use_cases import (
    GetRunDiffUseCase,
    GetRunReportUseCase,
    GetRunUseCase,
    ListRunsUseCase,
    RollbackRunUseCase,
    StartRunCommand,
    StartRunUseCase,
    StopRunUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.prompt_optimizer.run_manager import RunManager
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/prompt-optimizer",
    tags=["prompt-optimizer"],
)


# --- Request/Response Schemas ---


class StartRunRequest(BaseModel):
    dataset_id: str
    max_iterations: int = 20
    patience: int = 5
    budget: int = 200
    dry_run: bool = False


class StartRunResponse(BaseModel):
    run_id: str
    status: str = "running"


class RunSummaryResponse(BaseModel):
    run_id: str
    tenant_id: str
    dataset_id: str
    dataset_name: str
    target_field: str
    bot_id: str | None
    run_type: str = "optimization"  # "optimization" | "validation"
    status: str
    baseline_score: float
    best_score: float
    current_iteration: int
    max_iterations: int
    total_api_calls: int
    stopped_reason: str
    started_at: str
    completed_at: str | None


class IterationResponse(BaseModel):
    iteration: int
    score: float
    passed_count: int
    total_count: int
    is_best: bool
    details: dict[str, Any] | None
    created_at: str


class RunDetailResponse(BaseModel):
    run_id: str
    tenant_id: str
    target_field: str
    bot_id: str | None
    status: str
    baseline_score: float
    best_score: float
    stopped_reason: str
    current_iteration: int
    max_iterations: int
    total_api_calls: int
    started_at: str
    iterations: list[IterationResponse]


class RollbackRequest(BaseModel):
    iteration: int


class RollbackResponse(BaseModel):
    run_id: str
    iteration: int
    prompt_snapshot: str
    score: float
    applied: bool


class DiffResponse(BaseModel):
    run_id: str
    iteration: int
    baseline_prompt: str
    iteration_prompt: str
    baseline_score: float
    iteration_score: float
    is_best: bool


# --- Endpoints ---


@router.post(
    "/runs",
    response_model=StartRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def start_run(
    body: StartRunRequest,
    request: Request,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: StartRunUseCase = Depends(
        Provide[Container.start_run_use_case]
    ),
) -> StartRunResponse:
    """Start an optimization run (async background task)."""
    auth_header = request.headers.get("authorization", "")
    api_token = auth_header.removeprefix("Bearer ").strip()
    command = StartRunCommand(
        tenant_id=tenant.tenant_id,
        dataset_id=body.dataset_id,
        api_token=api_token,
        max_iterations=body.max_iterations,
        patience=body.patience,
        budget=body.budget,
        dry_run=body.dry_run,
    )
    run_id = await use_case.execute(command)
    return StartRunResponse(run_id=run_id, status="running")


@router.get("/runs", response_model=PaginatedResponse[RunSummaryResponse])
@inject
async def list_runs(
    pagination: PaginationQuery = Depends(),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListRunsUseCase = Depends(
        Provide[Container.list_runs_use_case]
    ),
) -> PaginatedResponse[RunSummaryResponse]:
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size

    tenant_id = None if tenant.role == "system_admin" else tenant.tenant_id
    runs = await use_case.execute(tenant_id, limit=limit, offset=offset)
    total = await use_case.count(tenant_id)
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0

    return PaginatedResponse(
        items=[RunSummaryResponse(**r) for r in runs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
@inject
async def get_run(
    run_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetRunUseCase = Depends(
        Provide[Container.get_run_use_case]
    ),
) -> RunDetailResponse:
    try:
        result = await use_case.execute(run_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return RunDetailResponse(**result)


@router.post("/runs/{run_id}/stop", status_code=status.HTTP_200_OK)
@inject
async def stop_run(
    run_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: StopRunUseCase = Depends(
        Provide[Container.stop_run_use_case]
    ),
) -> dict:
    try:
        await use_case.execute(run_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return {"status": "stopped", "run_id": run_id}


@router.post("/runs/{run_id}/rollback", response_model=RollbackResponse)
@inject
async def rollback_run(
    run_id: str,
    body: RollbackRequest,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: RollbackRunUseCase = Depends(
        Provide[Container.rollback_run_use_case]
    ),
) -> RollbackResponse:
    try:
        result = await use_case.execute(run_id, body.iteration)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return RollbackResponse(**result)


@router.get("/runs/{run_id}/report")
@inject
async def get_run_report(
    run_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetRunReportUseCase = Depends(
        Provide[Container.get_run_report_use_case]
    ),
) -> dict:
    try:
        report = await use_case.execute(run_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return {"run_id": run_id, "report": report}


@router.get("/runs/{run_id}/diff/{iteration}", response_model=DiffResponse)
@inject
async def get_run_diff(
    run_id: str,
    iteration: int,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetRunDiffUseCase = Depends(
        Provide[Container.get_run_diff_use_case]
    ),
) -> DiffResponse:
    try:
        result = await use_case.execute(run_id, iteration)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return DiffResponse(**result)


@router.get("/runs/{run_id}/progress")
@inject
async def stream_progress(
    run_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    run_manager: RunManager = Depends(
        Provide[Container.run_manager]
    ),
) -> StreamingResponse:
    """SSE stream for real-time run progress."""
    return StreamingResponse(
        run_manager.subscribe_progress(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
