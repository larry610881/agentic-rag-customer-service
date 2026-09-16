from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.application.auth.api_key_use_cases import (
    ExchangeClientCredentialsUseCase,
)
from src.application.auth.change_password_use_case import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
    SameAsOldPasswordError,
)
from src.application.auth.login_use_case import (
    AccountLockedError,
    AuthenticationError,
    LoginCommand,
    LoginUseCase,
)
from src.application.auth.refresh_token_use_case import (
    InvalidRefreshTokenError,
    RefreshTokenUseCase,
)
from src.application.auth.register_user_use_case import (
    RegisterUserCommand,
    RegisterUserUseCase,
)
from src.container import Container
from src.domain.auth.api_key import InvalidClientError, InvalidScopeError
from src.domain.auth.registration_policy import can_register
from src.domain.auth.value_objects import Role
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.logging.trace import trace_step
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.errors import ApiError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class ClientCredentialsRequest(BaseModel):
    grant_type: str = ""
    client_id: str = ""
    client_secret: str = ""
    scope: str | None = None


class ClientCredentialsResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


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


@router.post("/token", response_model=ClientCredentialsResponse)
@inject
async def create_token(
    body: ClientCredentialsRequest,
    use_case: ExchangeClientCredentialsUseCase = Depends(
        Provide[Container.exchange_client_credentials_use_case]
    ),
) -> ClientCredentialsResponse:
    """OAuth2 client_credentials（Issue #67 P2）。

    client_id + client_secret → api_access 票。

    機器票 15 分鐘、不發 refresh；到期用 secret 再換。invalid_client 對不存在 /
    secret 錯 / 已撤銷 / 已過期一律同一訊息。舊的「給 tenant_id 就發票」已移除。
    """
    if body.grant_type != "client_credentials":
        raise ApiError(
            400,
            code="unsupported_grant_type",
        )
    try:
        result = await use_case.execute(
            client_id=body.client_id,
            client_secret=body.client_secret,
            scope=body.scope,
        )
    except InvalidClientError:
        raise ApiError(
            401,
            code="invalid_client",
        ) from None
    except InvalidScopeError:
        raise ApiError(
            403,
            code="invalid_scope",
        ) from None
    return ClientCredentialsResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        scope=result.scope,
    )


@router.post("/login", response_model=TokenResponse)
@inject
async def login(
    body: LoginRequest,
    use_case: LoginUseCase = Depends(Provide[Container.login_use_case]),
) -> TokenResponse:
    """email + 密碼登入（Issue #67 P5：development 免密碼租戶名稱登入已移除）。"""
    command = LoginCommand(email=body.account, password=body.password)
    try:
        with trace_step("login_use_case"):
            result = await use_case.execute(command)
    except AccountLockedError as e:
        # Issue #58：訊息刻意不提帳號存在與否，避免帳號列舉
        raise ApiError(
            429,
            code="too_many_login_attempts",
            message="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(e.retry_after)},
        ) from None
    except AuthenticationError:
        raise ApiError(
            401,
            code="invalid_credentials",
            message="Invalid credentials",
        ) from None
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
@inject
async def register(
    body: RegisterRequest,
    current: CurrentTenant = Depends(get_current_tenant),
    use_case: RegisterUserUseCase = Depends(
        Provide[Container.register_user_use_case]
    ),
) -> UserResponse:
    """建立使用者（邀請制，Issue #67）。

    system_admin 可建任何角色；tenant_admin 只能在自己租戶建 user / tenant_admin；
    其餘身分 403。自助公開註冊已移除。
    """
    try:
        target_role = Role(body.role)
    except ValueError:
        raise ApiError(
            422,
            code="invalid_role",
            message=f"Unknown role: {body.role}",
        ) from None
    if not can_register(
        actor_role=current.role,
        actor_tenant_id=current.tenant_id or None,
        target_role=target_role,
        target_tenant_id=body.tenant_id,
    ):
        raise ApiError(
            403,
            code="role_not_allowed",
            message="Not allowed to create a user with this role in this tenant",
        )
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
    use_case: RefreshTokenUseCase = Depends(
        Provide[Container.refresh_token_use_case]
    ),
) -> TokenResponse:
    """Refresh 換票（Issue #67 P3）。

    每次旋轉；重用舊票 → 整個 family 撤銷；ver 不符 → 401。
    """
    try:
        result = await use_case.execute(body.refresh_token)
    except InvalidRefreshTokenError as e:
        raise ApiError(
            401,
            code="invalid_refresh_token",
            message=e.message,
        ) from None
    return TokenResponse(
        access_token=result.access_token, refresh_token=result.refresh_token
    )


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
        raise ApiError(
            401,
            code="user_token_required",
            message="Change password requires a user-level JWT (not tenant token)",
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
        raise ApiError(
            400,
            code="wrong_password",
            message="舊密碼錯誤",
        ) from None
    except EntityNotFoundError:
        raise ApiError(
            404,
            code="user_not_found",
            message="使用者不存在",
        ) from None
    except SameAsOldPasswordError:
        raise ApiError(
            422,
            code="password_same_as_old",
            message="新密碼不可與舊密碼相同",
        ) from None
