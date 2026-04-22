"""Admin Pricing Router — S-Pricing.1 (system_admin only)."""

from __future__ import annotations

import logging
from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.application.pricing.create_pricing_use_case import (
    CreatePricingCommand,
    CreatePricingUseCase,
)
from src.application.pricing.deactivate_pricing_use_case import (
    DeactivatePricingCommand,
    DeactivatePricingUseCase,
)
from src.application.pricing.dry_run_recalculate_use_case import (
    DryRunRecalculateCommand,
    DryRunRecalculateUseCase,
)
from src.application.pricing.execute_recalculate_use_case import (
    ExecuteRecalculateCommand,
    ExecuteRecalculateUseCase,
)
from src.application.pricing.list_pricing_use_case import ListPricingUseCase
from src.application.pricing.list_recalc_history_use_case import (
    ListRecalcHistoryUseCase,
)
from src.container import Container
from src.domain.pricing.entity import ModelPricing, PricingRecalcAudit
from src.domain.pricing.value_objects import PricingCategory
from src.infrastructure.pricing.pricing_cache import InMemoryPricingCache
from src.interfaces.api.deps import CurrentTenant, require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/pricing",
    tags=["admin-pricing"],
)


# ---------------- Pydantic Schemas ----------------


class PricingResponse(BaseModel):
    id: str
    provider: str
    model_id: str
    display_name: str
    category: str
    input_price: float
    output_price: float
    cache_read_price: float
    cache_creation_price: float
    effective_from: datetime
    effective_to: datetime | None
    created_by: str
    created_at: datetime
    note: str | None


class CreatePricingRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(default="llm", description="'llm' or 'embedding'")
    input_price: float = Field(..., ge=0)
    output_price: float = Field(..., ge=0)
    cache_read_price: float = Field(default=0.0, ge=0)
    cache_creation_price: float = Field(default=0.0, ge=0)
    effective_from: datetime
    note: str = Field(..., min_length=1, description="改價理由（必填）")


class DryRunRecalculateRequest(BaseModel):
    pricing_id: str
    recalc_from: datetime
    recalc_to: datetime


class DryRunRecalculateResponse(BaseModel):
    dry_run_token: str
    pricing_id: str
    affected_rows: int
    cost_before_total: float
    cost_after_total: float
    cost_delta: float
    recalc_from: datetime
    recalc_to: datetime


class ExecuteRecalculateRequest(BaseModel):
    dry_run_token: str
    reason: str = Field(..., min_length=1)


class ExecuteRecalculateResponse(BaseModel):
    audit_id: str
    affected_rows: int
    cost_before_total: float
    cost_after_total: float


class RecalcAuditResponse(BaseModel):
    id: str
    pricing_id: str
    recalc_from: datetime
    recalc_to: datetime
    affected_rows: int
    cost_before_total: float
    cost_after_total: float
    cost_delta: float
    executed_by: str
    executed_at: datetime
    reason: str


def _to_response(p: ModelPricing) -> PricingResponse:
    return PricingResponse(
        id=p.id,
        provider=p.provider,
        model_id=p.model_id,
        display_name=p.display_name,
        category=p.category.value,
        input_price=p.rate.input_price,
        output_price=p.rate.output_price,
        cache_read_price=p.rate.cache_read_price,
        cache_creation_price=p.rate.cache_creation_price,
        effective_from=p.effective_from,
        effective_to=p.effective_to,
        created_by=p.created_by,
        created_at=p.created_at,
        note=p.note,
    )


def _audit_to_response(a: PricingRecalcAudit) -> RecalcAuditResponse:
    return RecalcAuditResponse(
        id=a.id,
        pricing_id=a.pricing_id,
        recalc_from=a.recalc_from,
        recalc_to=a.recalc_to,
        affected_rows=a.affected_rows,
        cost_before_total=a.cost_before_total,
        cost_after_total=a.cost_after_total,
        cost_delta=a.cost_delta,
        executed_by=a.executed_by,
        executed_at=a.executed_at,
        reason=a.reason,
    )


# ---------------- Endpoints ----------------


@router.get("", response_model=list[PricingResponse])
@inject
async def list_pricing(
    provider: str | None = None,
    category: str | None = None,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListPricingUseCase = Depends(
        Provide[Container.list_pricing_use_case]
    ),
) -> list[PricingResponse]:
    pricings = await use_case.execute(provider=provider, category=category)
    return [_to_response(p) for p in pricings]


@router.post(
    "",
    response_model=PricingResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_pricing(
    body: CreatePricingRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: CreatePricingUseCase = Depends(
        Provide[Container.create_pricing_use_case]
    ),
    cache: InMemoryPricingCache = Depends(Provide[Container.pricing_cache]),
) -> PricingResponse:
    try:
        pricing = await use_case.execute(
            CreatePricingCommand(
                provider=body.provider,
                model_id=body.model_id,
                display_name=body.display_name,
                category=PricingCategory(body.category),
                input_price=body.input_price,
                output_price=body.output_price,
                cache_read_price=body.cache_read_price,
                cache_creation_price=body.cache_creation_price,
                effective_from=body.effective_from,
                note=body.note,
                created_by=admin.user_id or admin.tenant_id or "unknown",
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 刷新 in-memory cache，讓新價立即生效
    await cache.refresh()
    return _to_response(pricing)


@router.post("/{pricing_id}/deactivate", response_model=PricingResponse)
@inject
async def deactivate_pricing(
    pricing_id: str,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: DeactivatePricingUseCase = Depends(
        Provide[Container.deactivate_pricing_use_case]
    ),
    list_use_case: ListPricingUseCase = Depends(
        Provide[Container.list_pricing_use_case]
    ),
    cache: InMemoryPricingCache = Depends(Provide[Container.pricing_cache]),
) -> PricingResponse:
    try:
        await use_case.execute(
            DeactivatePricingCommand(
                pricing_id=pricing_id,
                actor=admin.user_id or admin.tenant_id or "unknown",
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    await cache.refresh()
    # 回傳更新後狀態
    pricings = await list_use_case.execute()
    for p in pricings:
        if p.id == pricing_id:
            return _to_response(p)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="pricing not found"
    )


@router.post(
    "/recalculate:dry-run", response_model=DryRunRecalculateResponse
)
@inject
async def recalculate_dry_run(
    body: DryRunRecalculateRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: DryRunRecalculateUseCase = Depends(
        Provide[Container.dry_run_recalculate_use_case]
    ),
) -> DryRunRecalculateResponse:
    try:
        result = await use_case.execute(
            DryRunRecalculateCommand(
                pricing_id=body.pricing_id,
                recalc_from=body.recalc_from,
                recalc_to=body.recalc_to,
                actor=admin.user_id or admin.tenant_id or "unknown",
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return DryRunRecalculateResponse(
        dry_run_token=result.dry_run_token,
        pricing_id=result.pricing_id,
        affected_rows=result.affected_rows,
        cost_before_total=result.cost_before_total,
        cost_after_total=result.cost_after_total,
        cost_delta=result.cost_delta,
        recalc_from=result.recalc_from,
        recalc_to=result.recalc_to,
    )


@router.post(
    "/recalculate:execute", response_model=ExecuteRecalculateResponse
)
@inject
async def recalculate_execute(
    body: ExecuteRecalculateRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ExecuteRecalculateUseCase = Depends(
        Provide[Container.execute_recalculate_use_case]
    ),
) -> ExecuteRecalculateResponse:
    try:
        result = await use_case.execute(
            ExecuteRecalculateCommand(
                dry_run_token=body.dry_run_token,
                reason=body.reason,
                actor=admin.user_id or admin.tenant_id or "unknown",
            )
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        # race detected
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return ExecuteRecalculateResponse(
        audit_id=result.audit_id,
        affected_rows=result.affected_rows,
        cost_before_total=result.cost_before_total,
        cost_after_total=result.cost_after_total,
    )


@router.get(
    "/recalculate-history", response_model=list[RecalcAuditResponse]
)
@inject
async def recalculate_history(
    limit: int = 100,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListRecalcHistoryUseCase = Depends(
        Provide[Container.list_recalc_history_use_case]
    ),
) -> list[RecalcAuditResponse]:
    audits = await use_case.execute(limit=limit)
    return [_audit_to_response(a) for a in audits]
