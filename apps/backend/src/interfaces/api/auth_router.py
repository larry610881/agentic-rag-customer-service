from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.container import Container
from src.infrastructure.auth.jwt_service import JWTService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    tenant_id: str


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
