from dataclasses import dataclass
from typing import Callable

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.container import Container
from src.infrastructure.auth.jwt_service import JWTService

bearer_scheme = HTTPBearer()


@dataclass
class CurrentTenant:
    tenant_id: str
    user_id: str | None = None
    role: str | None = None


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

    token_type = payload.get("type", "tenant_access")

    if token_type == "user_access":
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        role = payload.get("role")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user_id",
            )
        return CurrentTenant(
            tenant_id=tenant_id or "",
            user_id=user_id,
            role=role,
        )

    # Legacy tenant_access token
    tenant_id = payload.get("sub")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing tenant_id",
        )
    return CurrentTenant(tenant_id=tenant_id)


def require_role(*roles: str) -> Callable:
    async def _check(
        tenant: CurrentTenant = Depends(get_current_tenant),
    ) -> CurrentTenant:
        if tenant.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(roles)}",
            )
        return tenant

    return _check
