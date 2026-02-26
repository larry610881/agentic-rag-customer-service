from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.application.auth.login_use_case import (
    AuthenticationError,
    LoginCommand,
    LoginUseCase,
)
from src.application.auth.register_user_use_case import (
    RegisterUserCommand,
    RegisterUserUseCase,
)
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


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str = "user"
    tenant_id: str | None = None


class UserLoginRequest(BaseModel):
    email: str
    password: str


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


@router.post("/user-login", response_model=TokenResponse)
@inject
async def user_login(
    body: UserLoginRequest,
    use_case: LoginUseCase = Depends(Provide[Container.login_use_case]),
) -> TokenResponse:
    """Login with email/password, returns JWT with user_id + tenant_id + role."""
    command = LoginCommand(email=body.email, password=body.password)
    try:
        result = await use_case.execute(command)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid credentials") from None
    return TokenResponse(access_token=result.access_token)
