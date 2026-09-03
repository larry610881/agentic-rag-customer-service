"""Session 撤銷端點 BDD Step Definitions（Issue #67 P3）— create_app + 記憶體儲存。"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.auth.entity import User
from src.domain.auth.value_objects import Email, Role, UserId
from src.infrastructure.auth.in_memory_token_stores import (
    InMemoryRefreshTokenStore,
    InMemoryTokenRevocationStore,
)

scenarios("unit/security/session_revocation.feature")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def session_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


@pytest.fixture
def context():
    return {}


@given("已啟動的 session 測試應用")
def app_ready(context, session_app):
    c = session_app.container
    user = User(
        id=UserId(value="u1"), tenant_id="t1", email=Email("u1@test.com"),
        hashed_password="x", role=Role.USER, token_version=1,
    )
    users = AsyncMock()
    users.find_by_id.return_value = user
    bots = AsyncMock()
    bots.execute.return_value = []
    bots.count.return_value = 0
    revocation = InMemoryTokenRevocationStore()
    refresh_store = InMemoryRefreshTokenStore()
    overrides = {
        c.user_repository: users,
        c.list_bots_use_case: bots,
        c.token_revocation_store: revocation,
        c.refresh_token_store: refresh_store,
    }
    for provider, obj in overrides.items():
        provider.override(providers.Object(obj))
    context.update(
        client=TestClient(session_app), jwt=c.jwt_service(), revocation=revocation,
        refresh_store=refresh_store, overrides=overrides,
    )
    yield
    for provider in overrides:
        provider.reset_override()


@given(parsers.parse(
    '使用者 "{user_id}" 租戶 "{tenant}" 持有 ver {ver:d} 的 access 票'
))
def access_token(context, user_id, tenant, ver):
    context["access"] = context["jwt"].create_user_token(
        user_id, tenant, "user", version=ver
    )


@given(parsers.parse('使用者 "{user_id}" 租戶 "{tenant}" 持有已登記的 refresh 票'))
def refresh_token(context, user_id, tenant):
    family, jti = "fam-1", "jti-1"
    context["refresh"] = context["jwt"].create_refresh_token(
        user_id, tenant, "user", version=1, family=family, jti=jti
    )
    context["original_refresh"] = context["refresh"]
    _run(context["refresh_store"].begin(family, jti, 3600))


@when(parsers.parse('撤銷儲存記錄 "{user_id}" 最低 ver 為 {ver:d}'))
def revoke(context, user_id, ver):
    _run(context["revocation"].revoke_user_before(user_id, ver, 900))


@when(parsers.parse("以該 access 票請求 GET {path}"))
def get_with_access(context, path):
    context["resp"] = context["client"].get(
        path, headers={"Authorization": f"Bearer {context['access']}"}
    )


def _post_refresh(context, token):
    context["resp"] = context["client"].post(
        "/api/v1/auth/refresh", json={"refresh_token": token}
    )
    if context["resp"].status_code == 200:
        context["refresh"] = context["resp"].json()["refresh_token"]


@when("以該 refresh 票呼叫 /auth/refresh")
def post_refresh(context):
    _post_refresh(context, context["refresh"])


@when("以原本的 refresh 票再呼叫 /auth/refresh")
def post_refresh_original(context):
    _post_refresh(context, context["original_refresh"])


@when("以新的 refresh 票呼叫 /auth/refresh")
def post_refresh_new(context):
    _post_refresh(context, context["refresh"])


@when("以該 access 票當 refresh 呼叫 /auth/refresh")
def post_refresh_with_access(context):
    _post_refresh(context, context["access"])


@then(parsers.parse("session 回應狀態碼為 {status:d}"))
def status_is(context, status):
    assert context["resp"].status_code == status, context["resp"].text


@then("回應含新的 access 與 refresh 票")
def new_pair(context):
    body = context["resp"].json()
    assert body["access_token"] and body["refresh_token"]
    assert body["refresh_token"] != context["original_refresh"]
    payload = context["jwt"].decode_token(body["refresh_token"])
    assert payload["family"] == "fam-1" and payload["jti"] != "jti-1"
