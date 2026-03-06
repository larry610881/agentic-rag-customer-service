from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.tenant.create_tenant_use_case import (
    CreateTenantCommand,
    CreateTenantUseCase,
)
from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.container import Container
from src.domain.shared.exceptions import DuplicateEntityError, EntityNotFoundError

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


class CreateTenantRequest(BaseModel):
    name: str
    plan: str = "starter"


class UpdateTenantAgentModesRequest(BaseModel):
    allowed_agent_modes: list[str]


class TenantResponse(BaseModel):
    id: str
    name: str
    plan: str
    allowed_agent_modes: list[str]
    created_at: str
    updated_at: str


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_tenant(
    body: CreateTenantRequest,
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
    return TenantResponse(
        id=tenant.id.value,
        name=tenant.name,
        plan=tenant.plan,
        allowed_agent_modes=tenant.allowed_agent_modes,
        created_at=tenant.created_at.isoformat(),
        updated_at=tenant.updated_at.isoformat(),
    )


@router.get("", response_model=list[TenantResponse])
@inject
async def list_tenants(
    use_case: ListTenantsUseCase = Depends(
        Provide[Container.list_tenants_use_case]
    ),
) -> list[TenantResponse]:
    tenants = await use_case.execute()
    return [
        TenantResponse(
            id=t.id.value,
            name=t.name,
            plan=t.plan,
            allowed_agent_modes=t.allowed_agent_modes,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
        )
        for t in tenants
    ]


@router.get("/{tenant_id}", response_model=TenantResponse)
@inject
async def get_tenant(
    tenant_id: str,
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
    return TenantResponse(
        id=tenant.id.value,
        name=tenant.name,
        plan=tenant.plan,
        allowed_agent_modes=tenant.allowed_agent_modes,
        created_at=tenant.created_at.isoformat(),
        updated_at=tenant.updated_at.isoformat(),
    )


_VALID_AGENT_MODES = {"router", "react"}


@router.patch("/{tenant_id}/agent-modes", response_model=TenantResponse)
@inject
async def update_tenant_agent_modes(
    tenant_id: str,
    body: UpdateTenantAgentModesRequest,
    use_case: GetTenantUseCase = Depends(
        Provide[Container.get_tenant_use_case]
    ),
    tenant_repo=Depends(Provide[Container.tenant_repository]),
) -> TenantResponse:
    invalid = set(body.allowed_agent_modes) - _VALID_AGENT_MODES
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent modes: {sorted(invalid)}. Must be one of {sorted(_VALID_AGENT_MODES)}",
        )
    try:
        tenant = await use_case.execute(tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    tenant.allowed_agent_modes = body.allowed_agent_modes
    await tenant_repo.save(tenant)
    return TenantResponse(
        id=tenant.id.value,
        name=tenant.name,
        plan=tenant.plan,
        allowed_agent_modes=tenant.allowed_agent_modes,
        created_at=tenant.created_at.isoformat(),
        updated_at=tenant.updated_at.isoformat(),
    )
