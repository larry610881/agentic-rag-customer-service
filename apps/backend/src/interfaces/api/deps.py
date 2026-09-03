"""API 認證相依（Issue #67）

三種 bearer 票：
- user_access（人，email+密碼登入）→ CurrentTenant(user_id, role)
- tenant_access（legacy 租戶票）→ CurrentTenant(tenant_id)
- api_access（機器，client_credentials）→ CurrentTenant(role="api_client", client_id,
  scopes, bot_ids)；只有掛 `require_scope(...)` 的端點接受，
  其餘一律 403 insufficient_scope。
"""

from dataclasses import dataclass
from typing import Callable

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.application.auth.api_key_use_cases import AuthenticateApiClientUseCase
from src.container import Container
from src.domain.auth.api_key import API_CLIENT_ROLE, InvalidClientError
from src.infrastructure.auth.jwt_service import API_ACCESS_TOKEN_TYPE, JWTService

bearer_scheme = HTTPBearer()

INSUFFICIENT_SCOPE = "insufficient_scope"


@dataclass
class CurrentTenant:
    tenant_id: str
    user_id: str | None = None
    role: str | None = None
    client_id: str | None = None
    scopes: tuple[str, ...] = ()
    bot_ids: tuple[str, ...] = ()

    @property
    def is_api_client(self) -> bool:
        return self.role == API_CLIENT_ROLE

    def allows_bot(self, bot_id: str | None) -> bool:
        """api_client 綁 bot 範圍時，bot_id 必須在範圍內；人類使用者不受限。"""
        if not self.is_api_client or not self.bot_ids:
            return True
        return bot_id is not None and bot_id in self.bot_ids


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


@inject
async def authenticate(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
    api_client_auth: AuthenticateApiClientUseCase = Depends(
        Provide[Container.authenticate_api_client_use_case]
    ),
) -> CurrentTenant:
    """解析任何一種 access 票；不做端點層級授權。"""
    try:
        payload = jwt_service.decode_token(credentials.credentials)
    except ValueError:
        raise _unauthorized("Invalid or expired token") from None

    token_type = payload.get("type", "tenant_access")

    if token_type in ("refresh", "tenant_refresh"):
        raise _unauthorized("Refresh tokens cannot be used to access resources")

    if token_type == API_ACCESS_TOKEN_TYPE:
        try:
            principal = await api_client_auth.execute(payload)
        except InvalidClientError:
            raise _unauthorized("Invalid or revoked API credentials") from None
        return CurrentTenant(
            tenant_id=principal.tenant_id,
            role=API_CLIENT_ROLE,
            client_id=principal.client_id,
            scopes=principal.scopes,
            bot_ids=principal.bot_ids,
        )

    if token_type == "user_access":
        user_id = payload.get("sub")
        if not user_id:
            raise _unauthorized("Token missing user_id")
        return CurrentTenant(
            tenant_id=payload.get("tenant_id") or "",
            user_id=user_id,
            role=payload.get("role"),
        )

    # Legacy tenant_access token
    tenant_id = payload.get("sub")
    if not tenant_id:
        raise _unauthorized("Token missing tenant_id")
    return CurrentTenant(tenant_id=tenant_id)


async def get_current_tenant(
    tenant: CurrentTenant = Depends(authenticate),
) -> CurrentTenant:
    """人類 / legacy 租戶票。機器票不得進入未宣告 scope 的端點。"""
    if tenant.is_api_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=INSUFFICIENT_SCOPE
        )
    return tenant


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


def require_scope(*scopes: str) -> Callable:
    """端點宣告可接受的 api scope（任一即可）；人類使用者不受 scope 限制。"""

    async def _check(
        tenant: CurrentTenant = Depends(authenticate),
    ) -> CurrentTenant:
        if tenant.is_api_client and not any(s in tenant.scopes for s in scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=INSUFFICIENT_SCOPE
            )
        return tenant

    return _check


def ensure_bot_allowed(tenant: CurrentTenant, bot_id: str | None) -> None:
    if not tenant.allows_bot(bot_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=INSUFFICIENT_SCOPE
        )
