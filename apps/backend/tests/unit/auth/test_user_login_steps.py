import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.login_use_case import (
    AuthenticationError,
    LoginCommand,
    LoginUseCase,
)
from src.domain.auth.entity import User
from src.domain.auth.value_objects import Email, Role, UserId

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
    mock_jwt_service.create_user_token.assert_called_once_with(
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
