"""Bot 設定版本 API 端點（spec §8 / §13）

版本狀態機的 HTTP 介面：create / list / get / publish / reject / rollback。
InvalidVersionTransitionError → 409；StaticCheckFailedError → 400 + 逐項明細。
"""

from datetime import datetime
from math import ceil
from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from src.application.prompt_gate.gate_run_use_cases import (
    GateEstimateUseCase,
    GatePreconditionError,
    GetGateRunUseCase,
    StartGateRunUseCase,
)
from src.application.prompt_gate.replay_use_cases import (
    StartReplayCompareUseCase,
)
from src.application.prompt_gate.static_checks import StaticCheckFailedError
from src.application.prompt_gate.version_use_cases import (
    CreateConfigVersionCommand,
    CreateConfigVersionUseCase,
    GetConfigVersionUseCase,
    GetVersionMetricsUseCase,
    ListConfigVersionsUseCase,
    PublishConfigVersionUseCase,
    RejectConfigVersionUseCase,
    RollbackConfigVersionCommand,
    RollbackConfigVersionUseCase,
)
from src.container import Container
from src.domain.prompt_gate.entity import (
    GateBlockedError,
    InvalidVersionTransitionError,
)
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.interfaces.api.deps import (
    CurrentTenant,
    get_current_tenant,
    require_role,
)
from src.interfaces.api.schemas.pagination import PaginatedResponse

# H4：版本寫入/驗證端點限管理員角色。一般成員（role="user"，註冊預設）不得建立/
# 發布/回朔版本（等同租戶內權限提升寫入 bots 設定），亦不得觸發 validate/replay
# （每次燒 gate_daily_limit 且必因影子授權 403 全滅，可癱瘓當日正常驗證）。
_VERSION_WRITER = require_role("system_admin", "tenant_admin")

router = APIRouter(
    prefix="/api/v1/bots/{bot_id}/config-versions",
    tags=["bot-config-versions"],
)


class CreateVersionRequest(BaseModel):
    changes: dict[str, Any] = Field(
        ..., description="白名單欄位的部分更新（key ∈ SNAPSHOT_FIELDS）"
    )


class RollbackRequest(BaseModel):
    target_version_id: str


class PublishRequest(BaseModel):
    # warn 模式驗證失敗後的強制發布（block 模式 force 無效，spec §4.1）
    force: bool = False


class GateRunResponse(BaseModel):
    id: str
    bot_id: str
    version_id: str
    status: str
    verdict: str | None
    fail_reasons: list[str]
    dataset_ids: list[str]
    repeats: int
    soft_threshold: float
    total_cases: int | None
    hard_failed_cases: int | None
    soft_pass_rate: float | None
    unstable_cases: int | None
    est_cost: float | None
    actual_cost: float | None
    details: dict | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


def _run_to_response(run) -> GateRunResponse:
    return GateRunResponse(
        id=run.id, bot_id=run.bot_id, version_id=run.version_id,
        status=run.status, verdict=run.verdict,
        fail_reasons=list(run.fail_reasons or []),
        dataset_ids=list(run.dataset_ids or []),
        repeats=run.repeats, soft_threshold=run.soft_threshold,
        total_cases=run.total_cases,
        hard_failed_cases=run.hard_failed_cases,
        soft_pass_rate=run.soft_pass_rate,
        unstable_cases=run.unstable_cases,
        est_cost=run.est_cost, actual_cost=run.actual_cost,
        details=run.details, error_message=run.error_message,
        created_at=run.created_at, started_at=run.started_at,
        completed_at=run.completed_at,
    )


class VersionResponse(BaseModel):
    id: str
    bot_id: str
    version_no: int
    status: str
    is_current: bool
    source: str
    source_run_id: str | None
    gate_run_id: str | None
    gate_verdict: str | None
    changed_fields: list[str]
    author_user_id: str | None
    published_at: datetime | None
    created_at: datetime


class VersionDetailResponse(VersionResponse):
    config_snapshot: dict[str, Any]
    snapshot_schema: int


def _to_response(version) -> VersionResponse:
    return VersionResponse(
        id=version.id,
        bot_id=version.bot_id,
        version_no=version.version_no,
        status=version.status,
        is_current=version.is_current,
        source=version.source,
        source_run_id=version.source_run_id,
        gate_run_id=version.gate_run_id,
        gate_verdict=version.gate_verdict,
        changed_fields=version.changed_fields,
        author_user_id=version.author_user_id,
        published_at=version.published_at,
        created_at=version.created_at,
    )


def _to_detail(version) -> VersionDetailResponse:
    return VersionDetailResponse(
        **_to_response(version).model_dump(),
        config_snapshot=version.config_snapshot,
        snapshot_schema=version.snapshot_schema,
    )


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
    if isinstance(exc, InvalidVersionTransitionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    if isinstance(exc, GateBlockedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    if isinstance(exc, GatePreconditionError):
        return HTTPException(
            status_code=exc.http_status,
            detail={"code": exc.code, "message": str(exc)},
        )
    if isinstance(exc, StaticCheckFailedError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "static_checks_failed",
                "violations": [
                    {"type": v.type, "detail": v.detail}
                    for v in exc.violations
                ],
            },
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    raise exc


@router.post(
    "", response_model=VersionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_version(
    bot_id: str,
    request: CreateVersionRequest,
    tenant: CurrentTenant = Depends(_VERSION_WRITER),
    use_case: CreateConfigVersionUseCase = Depends(
        Provide[Container.create_config_version_use_case]
    ),
) -> VersionDetailResponse:
    try:
        version = await use_case.execute(
            CreateConfigVersionCommand(
                tenant_id=tenant.tenant_id,
                bot_id=bot_id,
                changes=request.changes,
                author_user_id=tenant.user_id,
            )
        )
    except (
        EntityNotFoundError, StaticCheckFailedError, ValidationError,
    ) as exc:
        raise _handle(exc) from exc
    return _to_detail(version)


@router.get("", response_model=PaginatedResponse[VersionResponse])
@inject
async def list_versions(
    bot_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListConfigVersionsUseCase = Depends(
        Provide[Container.list_config_versions_use_case]
    ),
) -> PaginatedResponse[VersionResponse]:
    versions, total = await use_case.execute(
        tenant.tenant_id, bot_id,
        status=status_filter,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    total_pages = ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[_to_response(v) for v in versions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{version_id}", response_model=VersionDetailResponse)
@inject
async def get_version(
    bot_id: str,
    version_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetConfigVersionUseCase = Depends(
        Provide[Container.get_config_version_use_case]
    ),
) -> VersionDetailResponse:
    try:
        version = await use_case.execute(tenant.tenant_id, version_id)
    except EntityNotFoundError as exc:
        raise _handle(exc) from exc
    if version.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version does not belong to this bot",
        )
    return _to_detail(version)


@router.get("/{version_id}/metrics")
@inject
async def get_version_metrics(
    bot_id: str,
    version_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetVersionMetricsUseCase = Depends(
        Provide[Container.get_version_metrics_use_case]
    ),
) -> dict:
    """版本服役成效卡（§13.6）：方向性參考，非嚴格因果。"""
    try:
        m = await use_case.execute(tenant.tenant_id, version_id)
    except EntityNotFoundError as exc:
        raise _handle(exc) from exc
    return {
        "version_id": m.version_id,
        "message_count": m.message_count,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "total_cost": m.total_cost,
        "avg_latency_ms": m.avg_latency_ms,
        "eval_avg_by_layer": m.eval_avg_by_layer,
        "feedback_up": m.feedback_up,
        "feedback_down": m.feedback_down,
        "feedback_positive_rate": m.feedback_positive_rate,
    }


@router.post("/{version_id}/publish", response_model=VersionResponse)
@inject
async def publish_version(
    bot_id: str,
    version_id: str,
    body: PublishRequest | None = None,
    tenant: CurrentTenant = Depends(_VERSION_WRITER),
    use_case: PublishConfigVersionUseCase = Depends(
        Provide[Container.publish_config_version_use_case]
    ),
) -> VersionResponse:
    try:
        version = await use_case.execute(
            tenant.tenant_id, version_id,
            force=bool(body and body.force),
        )
    except (
        EntityNotFoundError,
        InvalidVersionTransitionError,
        GateBlockedError,
    ) as exc:
        raise _handle(exc) from exc
    return _to_response(version)


class ReplayCompareRequest(BaseModel):
    sample_size: int = Field(default=10, ge=1, le=30)


@router.post(
    "/{version_id}/replay-compare",
    response_model=GateRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def replay_compare_version(
    bot_id: str,
    version_id: str,
    request: Request,
    body: ReplayCompareRequest | None = None,
    tenant: CurrentTenant = Depends(_VERSION_WRITER),
    use_case: StartReplayCompareUseCase = Depends(
        Provide[Container.start_replay_compare_use_case]
    ),
) -> GateRunResponse:
    """Phase G — 真實流量回放 pairwise 對比（202 背景執行）。
    消耗 token 計入租戶（受測 ×2 + judge ×2 每題），與 gate 共用日限額/預算。"""
    auth = request.headers.get("authorization", "")
    api_token = auth.split(" ", 1)[1] if " " in auth else auth
    try:
        run = await use_case.execute(
            tenant_id=tenant.tenant_id,
            bot_id=bot_id,
            version_id=version_id,
            api_token=api_token,
            sample_size=body.sample_size if body else 10,
            triggered_by=tenant.user_id,
        )
    except (EntityNotFoundError, GatePreconditionError) as exc:
        raise _handle(exc) from exc
    return _run_to_response(run)


@router.post(
    "/{version_id}/validate",
    response_model=GateRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def validate_version(
    bot_id: str,
    version_id: str,
    request: Request,
    tenant: CurrentTenant = Depends(_VERSION_WRITER),
    use_case: StartGateRunUseCase = Depends(
        Provide[Container.start_gate_run_use_case]
    ),
) -> GateRunResponse:
    """202 啟動 gate run（背景執行，前端 polling GET /prompt-gate/runs/{id}）。
    JWT 剝下傳給背景任務回打 /agent/chat（/validate 先例）。"""
    auth = request.headers.get("authorization", "")
    api_token = auth.split(" ", 1)[1] if " " in auth else auth
    try:
        run = await use_case.execute(
            tenant_id=tenant.tenant_id,
            bot_id=bot_id,
            version_id=version_id,
            api_token=api_token,
            triggered_by=tenant.user_id,
        )
    except (
        EntityNotFoundError,
        InvalidVersionTransitionError,
        GatePreconditionError,
    ) as exc:
        raise _handle(exc) from exc
    return _run_to_response(run)


@router.post("/{version_id}/reject", response_model=VersionResponse)
@inject
async def reject_version(
    bot_id: str,
    version_id: str,
    tenant: CurrentTenant = Depends(_VERSION_WRITER),
    use_case: RejectConfigVersionUseCase = Depends(
        Provide[Container.reject_config_version_use_case]
    ),
) -> VersionResponse:
    try:
        version = await use_case.execute(tenant.tenant_id, version_id)
    except (EntityNotFoundError, InvalidVersionTransitionError) as exc:
        raise _handle(exc) from exc
    return _to_response(version)


@router.post("/rollback", response_model=VersionResponse)
@inject
async def rollback_version(
    bot_id: str,
    request: RollbackRequest,
    tenant: CurrentTenant = Depends(_VERSION_WRITER),
    use_case: RollbackConfigVersionUseCase = Depends(
        Provide[Container.rollback_config_version_use_case]
    ),
) -> VersionResponse:
    try:
        version = await use_case.execute(
            RollbackConfigVersionCommand(
                tenant_id=tenant.tenant_id,
                bot_id=bot_id,
                target_version_id=request.target_version_id,
                author_user_id=tenant.user_id,
            )
        )
    except (EntityNotFoundError, ValidationError) as exc:
        raise _handle(exc) from exc
    return _to_response(version)


# ── Gate run 查詢 / estimate（prefix 不同，掛第二個 router）──

gate_router = APIRouter(prefix="/api/v1", tags=["prompt-gate"])


@gate_router.get("/bots/{bot_id}/prompt-gate/estimate")
@inject
async def gate_estimate(
    bot_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GateEstimateUseCase = Depends(
        Provide[Container.gate_estimate_use_case]
    ),
) -> dict:
    try:
        return await use_case.execute(tenant.tenant_id, bot_id)
    except EntityNotFoundError as exc:
        raise _handle(exc) from exc


@gate_router.get(
    "/prompt-gate/runs/{run_id}", response_model=GateRunResponse
)
@inject
async def get_gate_run(
    run_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetGateRunUseCase = Depends(
        Provide[Container.get_gate_run_use_case]
    ),
) -> GateRunResponse:
    try:
        run = await use_case.execute(tenant.tenant_id, run_id)
    except EntityNotFoundError as exc:
        raise _handle(exc) from exc
    return _run_to_response(run)
