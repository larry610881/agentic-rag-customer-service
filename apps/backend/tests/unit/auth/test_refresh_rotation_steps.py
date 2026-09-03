"""Refresh 旋轉與撤銷 BDD Step Definitions（Issue #67 P3）— 用例層 + 記憶體儲存。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.change_password_use_case import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
)
from src.application.auth.login_use_case import LoginCommand, LoginUseCase
from src.application.auth.refresh_token_use_case import (
    InvalidRefreshTokenError,
    RefreshTokenUseCase,
)
from src.domain.auth.entity import User
from src.domain.auth.value_objects import Email, Role, UserId
from src.infrastructure.auth.in_memory_token_stores import (
    REVOKED,
    InMemoryRefreshTokenStore,
    InMemoryTokenRevocationStore,
)
from src.infrastructure.auth.jwt_service import JWTService

scenarios("unit/auth/refresh_rotation.feature")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def ctx():
    return {"jwt": JWTService("rotation-secret")}


@given(parsers.parse(
    '使用者 "{user_id}" 租戶 "{tenant}" 角色 "{role}" token_version {ver:d}'
))
def user(ctx, user_id, tenant, role, ver):
    ctx["user"] = User(
        id=UserId(value=user_id), tenant_id=tenant, email=Email("u@test.com"),
        hashed_password="hashed_OldPass123", role=Role(role), token_version=ver,
    )
    repo = AsyncMock()
    repo.find_by_id.side_effect = lambda _id: ctx["user"]
    repo.find_by_email.side_effect = lambda _e: ctx["user"]

    async def save(u):
        ctx["user"] = u

    repo.save.side_effect = save
    ctx["repo"] = repo
    pw = MagicMock()
    pw.verify_password.side_effect = lambda p, h: h == f"hashed_{p}"
    pw.hash_password.side_effect = lambda p: f"hashed_{p}"
    ctx["pw"] = pw


@given("記憶體版 refresh / 撤銷儲存")
def stores(ctx):
    ctx["refresh_store"] = InMemoryRefreshTokenStore()
    ctx["revocation"] = InMemoryTokenRevocationStore()
    ctx["refresh_uc"] = RefreshTokenUseCase(
        ctx["jwt"], ctx["repo"], refresh_store=ctx["refresh_store"]
    )


def _login(ctx):
    uc = LoginUseCase(
        user_repository=ctx["repo"], password_service=ctx["pw"],
        jwt_service=ctx["jwt"], refresh_token_store=ctx["refresh_store"],
    )
    return _run(uc.execute(LoginCommand(email="u@test.com", password="OldPass123")))


@given(parsers.parse('使用者 "{user_id}" 已登入取得 refresh 票'))
def logged_in(ctx, user_id):
    ctx["refresh"] = _login(ctx).refresh_token
    ctx["original_refresh"] = ctx["refresh"]


@given(parsers.parse('使用者 "{user_id}" 的 token_version 變為 {ver:d}'))
def bump_version(ctx, user_id, ver):
    ctx["user"].token_version = ver


@given(parsers.parse('一張使用者 "{user_id}" 無 family 的 refresh 票'))
def legacy_refresh(ctx, user_id):
    ctx["refresh"] = ctx["jwt"].create_refresh_token(user_id, "t1", "user")


@when(parsers.parse('使用者 "{user_id}" 以正確密碼登入'))
def do_login(ctx, user_id):
    ctx["login"] = _login(ctx)


@when("以該 refresh 票換票")
def do_refresh(ctx):
    _refresh(ctx, ctx["refresh"])


@when("再以原本的 refresh 票換票")
def do_refresh_original(ctx):
    _refresh(ctx, ctx["original_refresh"])


@when("以最新的 refresh 票換票")
def do_refresh_latest(ctx):
    _refresh(ctx, ctx["refresh"])


def _refresh(ctx, token):
    ctx.pop("error", None)
    try:
        ctx["result"] = _run(ctx["refresh_uc"].execute(token))
        ctx["previous_refresh"] = token
        ctx["refresh"] = ctx["result"].refresh_token
    except InvalidRefreshTokenError as e:
        ctx["error"] = e


@when(parsers.parse('使用者 "{user_id}" 以舊密碼 "{old}" 改為 "{new}"'))
def change_password(ctx, user_id, old, new):
    uc = ChangePasswordUseCase(
        user_repository=ctx["repo"], password_service=ctx["pw"],
        revocation_store=ctx["revocation"], access_ttl_seconds=900,
    )
    _run(uc.execute(ChangePasswordCommand(
        user_id=user_id, old_password=old, new_password=new,
    )))


@then("登入回傳的 refresh 票帶 family 與 jti 且 family 已登記")
def login_registered(ctx):
    payload = ctx["jwt"].decode_token(ctx["login"].refresh_token)
    assert payload["family"] and payload["jti"] and payload["ver"] == 1
    assert ctx["refresh_store"]._current(payload["family"]) == payload["jti"]


@then("換票成功且新的 refresh 票 family 相同 jti 不同")
def rotated(ctx):
    assert "error" not in ctx, ctx.get("error")
    old = ctx["jwt"].decode_token(ctx["previous_refresh"])
    new = ctx["jwt"].decode_token(ctx["result"].refresh_token)
    assert new["family"] == old["family"]
    assert new["jti"] != old["jti"]
    access = ctx["jwt"].decode_token(ctx["result"].access_token)
    assert access["type"] == "user_access" and access["ver"] == 1


@then("換票應失敗")
def refresh_failed(ctx):
    assert isinstance(ctx.get("error"), InvalidRefreshTokenError)


@then("family 已被撤銷")
def family_revoked(ctx):
    family = ctx["jwt"].decode_token(ctx["original_refresh"])["family"]
    assert ctx["refresh_store"]._current(family) == REVOKED


@then(parsers.parse('使用者 "{user_id}" 的 token_version 應為 {ver:d}'))
def version_is(ctx, user_id, ver):
    assert ctx["user"].token_version == ver
    assert ctx["user"].hashed_password == "hashed_NewPass456"


@then(parsers.parse('撤銷儲存記錄 "{user_id}" 最低 ver 為 {ver:d}'))
def revocation_recorded(ctx, user_id, ver):
    assert _run(ctx["revocation"].min_version(user_id)) == ver


@then("換票成功且新的 refresh 票帶 family")
def legacy_rotated(ctx):
    assert "error" not in ctx, ctx.get("error")
    new = ctx["jwt"].decode_token(ctx["result"].refresh_token)
    assert new["family"]
    assert ctx["refresh_store"]._current(new["family"]) == new["jti"]
