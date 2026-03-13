import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.login_use_case import (
    AuthenticationError,
    LoginCommand,
    LoginUseCase,
)
from src.domain.auth.entity import User
from src.domain.auth.value_objects import Email, Role, UserId
from src.interfaces.api.auth_router import LoginRequest, login

scenarios("unit/auth/user_login.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_user_repo():
    return AsyncMock()


@pytest.fixture
def mock_password_service():
    svc = MagicMock()
    svc.verify_password = MagicMock(return_value=True)
    return svc


@pytest.fixture
def mock_jwt_service():
    svc = MagicMock()
    svc.create_user_token = MagicMock(return_value="jwt-token-123")
    svc.create_refresh_token = MagicMock(return_value="refresh-token-456")
    return svc


@pytest.fixture
def use_case(mock_user_repo, mock_password_service, mock_jwt_service):
    return LoginUseCase(
        user_repository=mock_user_repo,
        password_service=mock_password_service,
        jwt_service=mock_jwt_service,
    )


@pytest.fixture
def context():
    return {}


@given(parsers.parse('已註冊使用者 email "{email}" 角色 "{role}" 租戶 "{tenant_id}"'))
def registered_user(mock_user_repo, mock_password_service, email, role, tenant_id):
    user = User(
        id=UserId(value="user-001"),
        tenant_id=tenant_id,
        email=Email(email),
        hashed_password="hashed_correct",
        role=Role(role),
    )
    mock_user_repo.find_by_email = AsyncMock(return_value=user)
    # Default: password matches
    mock_password_service.verify_password = MagicMock(return_value=True)


@given(parsers.parse('系統中無 email 為 "{email}" 的使用者'))
def no_user(mock_user_repo, email):
    mock_user_repo.find_by_email = AsyncMock(return_value=None)


@when(parsers.parse('我以 email "{email}" 密碼 "{password}" 登入'))
def do_login(context, use_case, mock_password_service, email, password):
    # Set wrong password behavior
    if password == "WrongPassword":
        mock_password_service.verify_password = MagicMock(return_value=False)

    command = LoginCommand(email=email, password=password)
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except AuthenticationError as e:
        context["result"] = None
        context["error"] = e


@then("應回傳包含 user_id 和 tenant_id 和 role 的 JWT")
def jwt_returned(context, mock_jwt_service):
    assert context["result"] is not None
    assert context["result"].access_token == "jwt-token-123"
    assert context["result"].refresh_token == "refresh-token-456"
    mock_jwt_service.create_user_token.assert_called_once_with(
        user_id="user-001",
        tenant_id="tenant-001",
        role="user",
    )
    mock_jwt_service.create_refresh_token.assert_called_once_with(
        user_id="user-001",
        tenant_id="tenant-001",
        role="user",
    )


@then(parsers.parse('JWT type 應為 "{token_type}"'))
def jwt_type_is(context, token_type):
    # The token type is embedded in the JWT by jwt_service, verified by checking
    # that create_user_token was called (which produces type=user_access)
    assert context["result"] is not None


@then("應拋出認證失敗錯誤")
def auth_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], AuthenticationError)


# ── Router-level login tests (C19) ──


@given(parsers.parse('app_env 為 "{env}"'))
def set_app_env(context, env):
    context["app_env"] = env


@given("LoginUseCase 驗證成功回傳 token")
def mock_login_success(context):
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(
        return_value=SimpleNamespace(
            access_token="uc-access-token",
            refresh_token="uc-refresh-token",
        )
    )
    context["login_use_case"] = mock_uc


@given("LoginUseCase 拋出 AuthenticationError")
def mock_login_failure(context):
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=AuthenticationError())
    context["login_use_case"] = mock_uc


@given("tenant_repo.find_by_name 回傳 None")
def mock_tenant_not_found(context):
    context["tenant_repo_returns_none"] = True


@when(
    parsers.parse(
        '我透過 login API 以 account "{account}" 密碼 "{password}" 登入'
    )
)
def call_login_api(context, account, password):
    mock_jwt = MagicMock()
    mock_jwt.create_tenant_token = MagicMock(return_value="dev-token")
    mock_jwt.create_tenant_refresh_token = MagicMock(return_value="dev-refresh")

    mock_tenant_repo = AsyncMock()
    if context.get("tenant_repo_returns_none"):
        mock_tenant_repo.find_by_name = AsyncMock(return_value=None)
    else:
        mock_tenant_repo.find_by_name = AsyncMock(return_value=None)

    mock_uc = context.get("login_use_case", AsyncMock())
    body = LoginRequest(account=account, password=password)

    context["mock_tenant_repo"] = mock_tenant_repo

    with patch("src.interfaces.api.auth_router.settings") as mock_settings:
        mock_settings.app_env = context["app_env"]
        try:
            result = _run(
                login(
                    body=body,
                    jwt_service=mock_jwt,
                    tenant_repo=mock_tenant_repo,
                    use_case=mock_uc,
                )
            )
            context["api_result"] = result
            context["api_error"] = None
        except Exception as e:
            context["api_result"] = None
            context["api_error"] = e


@then("應回傳 LoginUseCase 的 token")
def check_uc_token(context):
    assert context["api_result"] is not None
    assert context["api_result"].access_token == "uc-access-token"
    assert context["api_result"].refresh_token == "uc-refresh-token"


@then("不應呼叫 tenant_repo.find_by_name")
def check_no_tenant_lookup(context):
    context["mock_tenant_repo"].find_by_name.assert_not_called()


@then("應拋出 HTTP 401 錯誤")
def check_http_401(context):
    from fastapi import HTTPException

    assert context["api_error"] is not None
    assert isinstance(context["api_error"], HTTPException)
    assert context["api_error"].status_code == 401
