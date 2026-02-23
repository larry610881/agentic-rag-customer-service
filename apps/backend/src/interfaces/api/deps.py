from dataclasses import dataclass

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.container import Container
from src.infrastructure.auth.jwt_service import JWTService

bearer_scheme = HTTPBearer()


@dataclass
class CurrentTenant:
    tenant_id: str


@inject
async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
) -> CurrentTenant:
    try:
        payload = jwt_service.decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
    tenant_id = payload.get("sub")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing tenant_id",
        )
    return CurrentTenant(tenant_id=tenant_id)
