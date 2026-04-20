from math import ceil

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.ledger.get_tenant_quota_use_case import (
    GetTenantQuotaUseCase,
)
from src.application.tenant.create_tenant_use_case import (
    CreateTenantCommand,
    CreateTenantUseCase,
)
from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.application.tenant.update_tenant_use_case import (
    UpdateTenantCommand,
    UpdateTenantUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import (
    DomainException,
    DuplicateEntityError,
    EntityNotFoundError,
)
from src.domain.tenant.entity import Tenant
from src.interfaces.api.deps import CurrentTenant, get_current_tenant, require_role
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


class CreateTenantRequest(BaseModel):
    name: str
    plan: str = "starter"


class UpdateTenantConfigRequest(BaseModel):
    plan: str | None = None
    monthly_token_limit: int | None = None
    included_categories: list[str] | None = None
    default_ocr_model: str | None = None
    default_context_model: str | None = None
    default_classification_model: str | None = None


class TenantQuotaResponse(BaseModel):
    cycle_year_month: str
    plan_name: str
    base_total: int
    base_remaining: int
    addon_remaining: int
    total_remaining: int
    total_used_in_cycle: int
    included_categories: list[str] | None = None


class TenantResponse(BaseModel):
    id: str
    name: str
    plan: str
    monthly_token_limit: int | None = None
    included_categories: list[str] | None = None
    default_ocr_model: str = ""
    default_context_model: str = ""
    default_classification_model: str = ""
    created_at: str
    updated_at: str


def _to_response(t: Tenant) -> TenantResponse:
    return TenantResponse(
        id=t.id.value,
        name=t.name,
        plan=t.plan,
        monthly_token_limit=t.monthly_token_limit,
        included_categories=t.included_categories,
        default_ocr_model=t.default_ocr_model,
        default_context_model=t.default_context_model,
        default_classification_model=t.default_classification_model,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_tenant(
    body: CreateTenantRequest,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: CreateTenantUseCase = Depends(
        Provide[Container.create_tenant_use_case]
    ),
) -> TenantResponse:
    try:
        tenant = await use_case.execute(
            CreateTenantCommand(name=body.name, plan=body.plan)
        )
    except DuplicateEntityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=e.message
        ) from None
    return _to_response(tenant)


@router.get("", response_model=PaginatedResponse[TenantResponse])
@inject
async def list_tenants(
    pagination: PaginationQuery = Depends(),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListTenantsUseCase = Depends(
        Provide[Container.list_tenants_use_case]
    ),
    get_tenant_uc: GetTenantUseCase = Depends(
        Provide[Container.get_tenant_use_case]
    ),
) -> PaginatedResponse[TenantResponse]:
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size
    if tenant.role == "system_admin":
        tenants = await use_case.execute(limit=limit, offset=offset)
        total = await use_case.count()
    else:
        single = await get_tenant_uc.execute(tenant.tenant_id)
        tenants = [single]
        total = 1
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[_to_response(t) for t in tenants],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
@inject
async def get_tenant(
    tenant_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetTenantUseCase = Depends(
        Provide[Container.get_tenant_use_case]
    ),
) -> TenantResponse:
    try:
        tenant = await use_case.execute(tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return _to_response(tenant)


@router.patch("/{tenant_id}/config", response_model=TenantResponse)
@inject
async def update_tenant_config(
    tenant_id: str,
    body: UpdateTenantConfigRequest,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateTenantUseCase = Depends(
        Provide[Container.update_tenant_use_case]
    ),
) -> TenantResponse:
    try:
        tenant = await use_case.execute(
            UpdateTenantCommand(tenant_id=tenant_id, **body.model_dump())
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from None
    return _to_response(tenant)


@router.get("/{tenant_id}/quota", response_model=TenantQuotaResponse)
@inject
async def get_tenant_quota(
    tenant_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetTenantQuotaUseCase = Depends(
        Provide[Container.get_tenant_quota_use_case]
    ),
) -> TenantQuotaResponse:
    """回傳租戶本月額度狀態。系統 admin 可查任何租戶；非 admin 只能查自己。

    若本月 ledger 不存在會自動建立（從 plan + 上月 addon carryover）。
    """
    # Permission: 非 admin 只能看自己
    if tenant.role != "system_admin" and tenant.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other tenant's quota",
        )
    try:
        result = await use_case.execute(tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return TenantQuotaResponse(
        cycle_year_month=result.cycle_year_month,
        plan_name=result.plan_name,
        base_total=result.base_total,
        base_remaining=result.base_remaining,
        addon_remaining=result.addon_remaining,
        total_remaining=result.total_remaining,
        total_used_in_cycle=result.total_used_in_cycle,
        included_categories=result.included_categories,
    )
