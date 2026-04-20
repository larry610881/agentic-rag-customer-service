"""Plan Template REST API — S-Token-Gov.1

CRUD endpoints + assign 端點。所有端點限 system_admin。
prefix=/api/v1/admin/plans 對齊既有 admin 路徑慣例（mcp_server_router 等）。
"""

from decimal import Decimal

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.application.plan.assign_plan_to_tenant_use_case import (
    AssignPlanToTenantUseCase,
)
from src.application.plan.create_plan_use_case import (
    CreatePlanCommand,
    CreatePlanUseCase,
)
from src.application.plan.delete_plan_use_case import DeletePlanUseCase
from src.application.plan.get_plan_use_case import GetPlanUseCase
from src.application.plan.list_plans_use_case import ListPlansUseCase
from src.application.plan.update_plan_use_case import (
    UpdatePlanCommand,
    UpdatePlanUseCase,
)
from src.container import Container
from src.domain.plan.entity import Plan
from src.domain.shared.exceptions import DomainException, EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, require_role

router = APIRouter(prefix="/api/v1/admin/plans", tags=["admin-plans"])


class CreatePlanRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    base_monthly_tokens: int = Field(..., ge=0)
    addon_pack_tokens: int = Field(..., ge=0)
    base_price: Decimal = Field(..., ge=0)
    addon_price: Decimal = Field(..., ge=0)
    currency: str = "TWD"
    description: str | None = None
    is_active: bool = True


class UpdatePlanRequest(BaseModel):
    base_monthly_tokens: int | None = Field(default=None, ge=0)
    addon_pack_tokens: int | None = Field(default=None, ge=0)
    base_price: Decimal | None = Field(default=None, ge=0)
    addon_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    description: str | None = None
    is_active: bool | None = None


class PlanResponse(BaseModel):
    id: str
    name: str
    base_monthly_tokens: int
    addon_pack_tokens: int
    base_price: Decimal
    addon_price: Decimal
    currency: str
    description: str | None = None
    is_active: bool
    created_at: str
    updated_at: str


def _to_response(p: Plan) -> PlanResponse:
    return PlanResponse(
        id=p.id,
        name=p.name,
        base_monthly_tokens=p.base_monthly_tokens,
        addon_pack_tokens=p.addon_pack_tokens,
        base_price=p.base_price,
        addon_price=p.addon_price,
        currency=p.currency,
        description=p.description,
        is_active=p.is_active,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@router.get("", response_model=list[PlanResponse])
@inject
async def list_plans(
    include_inactive: bool = True,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListPlansUseCase = Depends(
        Provide[Container.list_plans_use_case]
    ),
) -> list[PlanResponse]:
    plans = await use_case.execute(include_inactive=include_inactive)
    return [_to_response(p) for p in plans]


@router.get("/{plan_id}", response_model=PlanResponse)
@inject
async def get_plan(
    plan_id: str,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetPlanUseCase = Depends(Provide[Container.get_plan_use_case]),
) -> PlanResponse:
    try:
        plan = await use_case.execute(plan_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return _to_response(plan)


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_plan(
    body: CreatePlanRequest,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: CreatePlanUseCase = Depends(
        Provide[Container.create_plan_use_case]
    ),
) -> PlanResponse:
    try:
        plan = await use_case.execute(CreatePlanCommand(**body.model_dump()))
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from None
    return _to_response(plan)


@router.patch("/{plan_id}", response_model=PlanResponse)
@inject
async def update_plan(
    plan_id: str,
    body: UpdatePlanRequest,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdatePlanUseCase = Depends(
        Provide[Container.update_plan_use_case]
    ),
) -> PlanResponse:
    try:
        plan = await use_case.execute(
            UpdatePlanCommand(plan_id=plan_id, **body.model_dump())
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from None
    return _to_response(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_plan(
    plan_id: str,
    force: bool = False,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: DeletePlanUseCase = Depends(
        Provide[Container.delete_plan_use_case]
    ),
) -> None:
    try:
        await use_case.execute(plan_id, force=force)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from None


@router.post("/{plan_name}/assign/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def assign_plan_to_tenant(
    plan_name: str,
    tenant_id: str,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: AssignPlanToTenantUseCase = Depends(
        Provide[Container.assign_plan_to_tenant_use_case]
    ),
) -> None:
    try:
        await use_case.execute(plan_name=plan_name, tenant_id=tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from None
