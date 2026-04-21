"""ChangePasswordUseCase — BDD Step Definitions (S-Auth.1)"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.change_password_use_case import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
    SameAsOldPasswordError,
)
from src.application.auth.login_use_case import AuthenticationError
from src.domain.auth.entity import User
from src.domain.auth.value_objects import Email, Role, UserId
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/auth/change_password.feature")


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
    # Default: old password matches when "OldPass123" is presented against its hash
    def verify(pw: str, hashed: str) -> bool:
        return pw == "OldPass123" and hashed == "hashed_OldPass123"
    svc.verify_password = MagicMock(side_effect=verify)
    svc.hash_password = MagicMock(side_effect=lambda p: f"hashed_{p}")
    return svc


@pytest.fixture
def use_case(mock_user_repo, mock_password_service):
    return ChangePasswordUseCase(
        user_repository=mock_user_repo,
        password_service=mock_password_service,
    )


@pytest.fixture
def context():
    return {}


@given(
    parsers.parse(
        '系統中存在使用者 "{user_id}" email "{email}" 密碼 "{password}" '
        '角色 "{role}" 租戶 "{tenant_id}"'
    )
)
def existing_user(
    context, mock_user_repo, user_id, email, password, role, tenant_id
):
    user = User(
        id=UserId(value=user_id),
        tenant_id=tenant_id,
        email=Email(email),
        hashed_password=f"hashed_{password}",
        role=Role(role),
    )
    context["seed_user"] = user

    async def _find(uid: str):
        if uid == user_id:
            return user
        return None

    mock_user_repo.find_by_id = AsyncMock(side_effect=_find)
    mock_user_repo.save = AsyncMock()


@when(
    parsers.parse(
        '我以 user_id "{user_id}" 舊密碼 "{old_password}" '
        '新密碼 "{new_password}" 變更密碼'
    )
)
def do_change_password(context, use_case, user_id, old_password, new_password):
    command = ChangePasswordCommand(
        user_id=user_id,
        old_password=old_password,
        new_password=new_password,
    )
    try:
        _run(use_case.execute(command))
        context["error"] = None
    except (
        AuthenticationError,
        EntityNotFoundError,
        SameAsOldPasswordError,
    ) as e:
        context["error"] = e


@then("變更應成功")
def change_succeeded(context):
    assert context["error"] is None


@then(
    parsers.parse(
        '使用者 "{user_id}" 的 hashed_password 應更新為 "{password}" 的 hash'
    )
)
def hash_updated(mock_user_repo, user_id, password):
    mock_user_repo.save.assert_awaited_once()
    saved: User = mock_user_repo.save.call_args.args[0]
    assert saved.id.value == user_id
    assert saved.hashed_password == f"hashed_{password}"


@then("應拋出認證失敗錯誤")
def auth_error(context):
    assert isinstance(context["error"], AuthenticationError)


@then(parsers.parse('使用者 "{user_id}" 的 hashed_password 不應被修改'))
def hash_not_modified(mock_user_repo, user_id):
    mock_user_repo.save.assert_not_awaited()


@then("應拋出 EntityNotFoundError")
def not_found_error(context):
    assert isinstance(context["error"], EntityNotFoundError)


@then("應拋出 SameAsOldPasswordError")
def same_password_error(context):
    assert isinstance(context["error"], SameAsOldPasswordError)
