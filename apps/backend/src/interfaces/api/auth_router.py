from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.container import Container
from src.domain.tenant.repository import TenantRepository
from src.infrastructure.auth.jwt_service import JWTService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    tenant_id: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TokenResponse)
@inject
async def create_token(
    body: TokenRequest,
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
) -> TokenResponse:
    """Dev-only endpoint: issue a JWT for a given tenant_id."""
    token = jwt_service.create_tenant_token(body.tenant_id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
@inject
async def login(
    body: LoginRequest,
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
    tenant_repo: TenantRepository = Depends(
        Provide[Container.tenant_repository]
    ),
) -> TokenResponse:
    """Dev-only login: username = tenant name, password = any non-empty."""
    tenant = await tenant_repo.find_by_name(body.username)
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt_service.create_tenant_token(tenant.id.value)
    return TokenResponse(access_token=token)
