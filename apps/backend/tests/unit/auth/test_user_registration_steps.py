import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.register_user_use_case import (
    RegisterUserCommand,
    RegisterUserUseCase,
)
from src.domain.auth.entity import TenantRequiredError
from src.domain.auth.value_objects import Email, Role, UserId
from src.domain.shared.exceptions import DuplicateEntityError

scenarios("unit/auth/user_registration.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_user_repo():
    repo = AsyncMock()
    repo.find_by_email = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_password_service():
    svc = MagicMock()
    svc.hash_password = MagicMock(return_value="hashed_password_123")
    return svc


@pytest.fixture
def use_case(mock_user_repo, mock_password_service):
    return RegisterUserUseCase(
        user_repository=mock_user_repo,
        password_service=mock_password_service,
    )


@pytest.fixture
def context():
    return {}


@given(parsers.parse('系統中尚未有 email 為 "{email}" 的使用者'))
def no_existing_user(mock_user_repo, email):
    mock_user_repo.find_by_email = AsyncMock(return_value=None)


@given(parsers.parse('存在租戶 "{tenant_id}"'))
def tenant_exists(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('系統中已有 email 為 "{email}" 的使用者'))
def existing_user(mock_user_repo, email):
    from src.domain.auth.entity import User

    existing = User(
        id=UserId(),
        tenant_id="tenant-001",
        email=Email(email),
        hashed_password="hashed",
        role=Role.USER,
    )
    mock_user_repo.find_by_email = AsyncMock(return_value=existing)


@when(
    parsers.parse(
        '我以 email "{email}" 密碼 "{password}" 角色 "{role}" 租戶 "{tenant_id}" 註冊'
    )
)
def register_user_with_tenant(context, use_case, email, password, role, tenant_id):
    command = RegisterUserCommand(
        email=email, password=password, role=role, tenant_id=tenant_id
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except (DuplicateEntityError, TenantRequiredError) as e:
        context["result"] = None
        context["error"] = e


@when(
    parsers.parse(
        '我以 email "{email}" 密碼 "{password}" 角色 "{role}" 無租戶 註冊'
    )
)
def register_user_no_tenant(context, use_case, email, password, role):
    command = RegisterUserCommand(
        email=email, password=password, role=role, tenant_id=None
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except (DuplicateEntityError, TenantRequiredError) as e:
        context["result"] = None
        context["error"] = e


@then("使用者應成功建立")
def user_created(context):
    assert context["result"] is not None
    assert context["error"] is None


@then(parsers.parse('使用者 email 應為 "{email}"'))
def user_email_is(context, email):
    assert context["result"].email.value == email


@then(parsers.parse('使用者角色應為 "{role}"'))
def user_role_is(context, role):
    assert context["result"].role.value == role


@then(parsers.parse('使用者租戶應為 "{tenant_id}"'))
def user_tenant_is(context, tenant_id):
    assert context["result"].tenant_id == tenant_id


@then("使用者租戶應為空")
def user_tenant_is_none(context):
    assert context["result"].tenant_id is None


@then("應拋出重複使用者錯誤")
def duplicate_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], DuplicateEntityError)


@then("應拋出缺少租戶錯誤")
def tenant_required_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], TenantRequiredError)
