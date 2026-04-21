from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.application.auth.change_password_use_case import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
    SameAsOldPasswordError,
)
from src.application.auth.login_use_case import (
    AuthenticationError,
    LoginCommand,
    LoginUseCase,
)
from src.application.auth.register_user_use_case import (
    RegisterUserCommand,
    RegisterUserUseCase,
)
from src.config import settings
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.tenant.repository import TenantRepository
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.logging.trace import trace_step
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TokenRequest(BaseModel):
    tenant_id: str


class LoginRequest(BaseModel):
    account: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "user"
    tenant_id: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    tenant_id: str | None = None


@router.post("/token", response_model=TokenResponse)
@inject
async def create_token(
    body: TokenRequest,
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
) -> TokenResponse:
    """Dev-only endpoint: issue a JWT for a given tenant_id."""
    token = jwt_service.create_tenant_token(body.tenant_id)
    refresh = jwt_service.create_tenant_refresh_token(body.tenant_id)
    return TokenResponse(access_token=token, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
@inject
async def login(
    body: LoginRequest,
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
    tenant_repo: TenantRepository = Depends(
        Provide[Container.tenant_repository]
    ),
    use_case: LoginUseCase = Depends(Provide[Container.login_use_case]),
) -> TokenResponse:
    """Unified login: dev mode uses tenant name, production uses email/password."""
    if settings.app_env == "development":
        with trace_step("find_by_name"):
            tenant = await tenant_repo.find_by_name(body.account)
        if tenant is not None:
            with trace_step("create_tenant_token"):
                token = jwt_service.create_tenant_token(tenant.id.value)
            with trace_step("create_tenant_refresh_token"):
                refresh = jwt_service.create_tenant_refresh_token(tenant.id.value)
            return TokenResponse(access_token=token, refresh_token=refresh)
        # Fallback to email/password login in dev mode

    # Production (or dev fallback): account = email, password verified via bcrypt
    command = LoginCommand(email=body.account, password=body.password)
    try:
        with trace_step("login_use_case"):
            result = await use_case.execute(command)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid credentials") from None
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
@inject
async def register(
    body: RegisterRequest,
    use_case: RegisterUserUseCase = Depends(
        Provide[Container.register_user_use_case]
    ),
) -> UserResponse:
    """Register a new user with email/password."""
    command = RegisterUserCommand(
        email=body.email,
        password=body.password,
        role=body.role,
        tenant_id=body.tenant_id,
    )
    user = await use_case.execute(command)
    return UserResponse(
        id=user.id.value,
        email=user.email.value,
        role=user.role.value,
        tenant_id=user.tenant_id,
    )


@router.post("/refresh", response_model=TokenResponse)
@inject
async def refresh_token(
    body: RefreshRequest,
    jwt_service: JWTService = Depends(Provide[Container.jwt_service]),
) -> TokenResponse:
    """Exchange a refresh token for a new access + refresh token pair."""
    try:
        payload = jwt_service.decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid or expired refresh token"
        ) from None

    token_type = payload.get("type")
    if token_type not in ("refresh", "tenant_refresh"):
        raise HTTPException(
            status_code=401, detail="Invalid token type for refresh"
        )

    sub = payload.get("sub", "")

    if token_type == "refresh":
        role = payload.get("role", "")
        tenant_id = payload.get("tenant_id")
        access = jwt_service.create_user_token(sub, tenant_id, role)
        refresh = jwt_service.create_refresh_token(sub, tenant_id, role)
    else:
        access = jwt_service.create_tenant_token(sub)
        refresh = jwt_service.create_tenant_refresh_token(sub)

    return TokenResponse(access_token=access, refresh_token=refresh)


# --- S-Auth.1: 租戶自助變更密碼 -----------------------------------------------


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password", status_code=204)
@inject
async def change_password(
    body: ChangePasswordRequest,
    current: CurrentTenant = Depends(get_current_tenant),
    use_case: ChangePasswordUseCase = Depends(
        Provide[Container.change_password_use_case]
    ),
) -> None:
    """登入中的使用者自行變更密碼 — 需 user_access JWT 且驗證舊密碼。"""
    if not current.user_id:
        raise HTTPException(
            status_code=401,
            detail="Change password requires a user-level JWT (not tenant token)",
        )
    command = ChangePasswordCommand(
        user_id=current.user_id,
        old_password=body.old_password,
        new_password=body.new_password,
    )
    try:
        await use_case.execute(command)
    except AuthenticationError:
        # 400（非 401）— 避免前端 apiFetch 把「舊密碼錯」
        # 誤判為 token 過期而觸發 refresh 迴圈
        raise HTTPException(status_code=400, detail="舊密碼錯誤") from None
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail="使用者不存在") from None
    except SameAsOldPasswordError:
        raise HTTPException(
            status_code=422, detail="新密碼不可與舊密碼相同"
        ) from None
