"""Admin User Management BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.delete_user_use_case import DeleteUserUseCase
from src.application.auth.list_users_use_case import ListUsersUseCase
from src.application.auth.reset_password_use_case import (
    ResetPasswordCommand,
    ResetPasswordUseCase,
)
from src.application.auth.update_user_use_case import (
    UpdateUserCommand,
    UpdateUserUseCase,
)
from src.domain.auth.entity import InvalidTenantBindingError, User
from src.domain.auth.value_objects import Email, Role, UserId
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/auth/admin_user_management.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_user(email: str, role: str, tenant_id: str) -> User:
    return User(
        id=UserId(),
        tenant_id=tenant_id,
        email=Email(email),
        hashed_password="hashed",
        role=Role(role),
    )


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_user_repo():
    return AsyncMock()


@pytest.fixture
def mock_password_service():
    svc = MagicMock()
    svc.hash_password = MagicMock(return_value="new_hashed_password")
    return svc


# --- Given ---


@given("系統中有以下使用者:", target_fixture="users")
def setup_users(context, mock_user_repo):
    users = [
        _make_user("admin@example.com", "system_admin", SYSTEM_TENANT_ID),
        _make_user("user1@example.com", "user", "tenant-001"),
        _make_user("user2@example.com", "tenant_admin", "tenant-002"),
    ]
    context["users"] = users

    # Build a lookup by email and id
    by_email = {u.email.value: u for u in users}
    by_id = {u.id.value: u for u in users}
    context["by_email"] = by_email
    context["by_id"] = by_id

    mock_user_repo.find_all = AsyncMock(return_value=users)
    mock_user_repo.find_all_by_tenant = AsyncMock(
        side_effect=lambda tid: [u for u in users if u.tenant_id == tid]
    )
    mock_user_repo.find_by_id = AsyncMock(
        side_effect=lambda uid: by_id.get(uid)
    )
    mock_user_repo.find_by_email = AsyncMock(
        side_effect=lambda e: by_email.get(e)
    )
    mock_user_repo.save = AsyncMock()
    mock_user_repo.delete = AsyncMock()
    return users


# --- When ---


@when("管理員列出所有使用者")
def list_all_users(context, mock_user_repo):
    use_case = ListUsersUseCase(user_repository=mock_user_repo)
    context["result"] = _run(use_case.execute())
    context["error"] = None


@when(parsers.parse('管理員列出租戶 "{tenant_id}" 的使用者'))
def list_users_by_tenant(context, mock_user_repo, tenant_id):
    use_case = ListUsersUseCase(user_repository=mock_user_repo)
    context["result"] = _run(use_case.execute(tenant_id))
    context["error"] = None


@when(parsers.parse('管理員將使用者 "{email}" 的角色更新為 "{role}"'))
def update_user_role(context, mock_user_repo, email, role):
    user = context["by_email"][email]
    use_case = UpdateUserUseCase(user_repository=mock_user_repo)
    try:
        context["result"] = _run(
            use_case.execute(UpdateUserCommand(user_id=user.id.value, role=role))
        )
        context["error"] = None
    except (InvalidTenantBindingError, EntityNotFoundError) as e:
        context["result"] = None
        context["error"] = e


@when(parsers.parse('管理員將使用者 "{email}" 的租戶更新為 "{tenant_id}"'))
def update_user_tenant(context, mock_user_repo, email, tenant_id):
    user = context["by_email"][email]
    use_case = UpdateUserUseCase(user_repository=mock_user_repo)
    try:
        context["result"] = _run(
            use_case.execute(
                UpdateUserCommand(user_id=user.id.value, tenant_id=tenant_id)
            )
        )
        context["error"] = None
    except (InvalidTenantBindingError, EntityNotFoundError) as e:
        context["result"] = None
        context["error"] = e


@when(
    parsers.parse(
        '管理員將使用者 "{email}" 的角色更新為 "{role}" 並租戶更新為 "{tenant_id}"'
    )
)
def update_user_role_and_tenant(context, mock_user_repo, email, role, tenant_id):
    user = context["by_email"][email]
    use_case = UpdateUserUseCase(user_repository=mock_user_repo)
    try:
        context["result"] = _run(
            use_case.execute(
                UpdateUserCommand(
                    user_id=user.id.value, role=role, tenant_id=tenant_id
                )
            )
        )
        context["error"] = None
    except (InvalidTenantBindingError, EntityNotFoundError) as e:
        context["result"] = None
        context["error"] = e


@when(parsers.parse('管理員刪除使用者 "{email}"'))
def delete_user_by_email(context, mock_user_repo, email):
    user = context["by_email"][email]
    use_case = DeleteUserUseCase(user_repository=mock_user_repo)
    try:
        _run(use_case.execute(user.id.value))
        context["deleted"] = True
        context["error"] = None
    except EntityNotFoundError as e:
        context["deleted"] = False
        context["error"] = e


@when(parsers.parse('管理員刪除使用者 ID 為 "{user_id}"'))
def delete_user_by_id(context, mock_user_repo, user_id):
    use_case = DeleteUserUseCase(user_repository=mock_user_repo)
    try:
        _run(use_case.execute(user_id))
        context["deleted"] = True
        context["error"] = None
    except EntityNotFoundError as e:
        context["deleted"] = False
        context["error"] = e


@when(parsers.parse('管理員重設使用者 "{email}" 的密碼為 "{password}"'))
def reset_password(context, mock_user_repo, mock_password_service, email, password):
    user = context["by_email"][email]
    use_case = ResetPasswordUseCase(
        user_repository=mock_user_repo,
        password_service=mock_password_service,
    )
    try:
        _run(use_case.execute(ResetPasswordCommand(user_id=user.id.value, new_password=password)))
        context["password_reset"] = True
        context["error"] = None
    except EntityNotFoundError as e:
        context["password_reset"] = False
        context["error"] = e


# --- Then ---


@then(parsers.parse("應回傳 {count:d} 位使用者"))
def verify_user_count(context, count):
    assert len(context["result"]) == count


@then(parsers.parse('使用者角色應更新為 "{role}"'))
def verify_role_updated(context, role):
    assert context["result"] is not None
    assert context["result"].role.value == role


@then(parsers.parse('使用者租戶應更新為 "{tenant_id}"'))
def verify_tenant_updated(context, tenant_id):
    assert context["result"] is not None
    assert context["result"].tenant_id == tenant_id


@then("應拋出無效租戶綁定錯誤")
def verify_invalid_binding_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], InvalidTenantBindingError)


@then("使用者應被刪除")
def verify_user_deleted(context, mock_user_repo):
    assert context["deleted"] is True
    mock_user_repo.delete.assert_called_once()


@then("應拋出使用者不存在錯誤")
def verify_user_not_found(context):
    assert context["error"] is not None
    assert isinstance(context["error"], EntityNotFoundError)


@then("使用者密碼應被更新")
def verify_password_reset(context, mock_user_repo):
    assert context["password_reset"] is True
    mock_user_repo.save.assert_called_once()
    saved_user = mock_user_repo.save.call_args[0][0]
    assert saved_user.hashed_password == "new_hashed_password"
