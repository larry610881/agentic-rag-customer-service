"""Auth API Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/auth/auth_api.feature")


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已存在租戶 "{name}"'))
def create_tenant(ctx, client, name):
    resp = client.post("/api/v1/tenants", json={"name": name})
    assert resp.status_code == 201, resp.text
    ctx["tenant_id"] = resp.json()["id"]


@given(
    parsers.parse('已註冊使用者 "{email}" 密碼 "{password}" 關聯該租戶')
)
def register_user(ctx, client, email, password):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_id": ctx["tenant_id"],
        },
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        '我送出 POST /api/v1/auth/register 帳號 "{email}" 密碼 "{password}" 關聯該租戶'
    )
)
def post_register(ctx, client, email, password):
    ctx["response"] = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_id": ctx.get("tenant_id"),
        },
    )


@when(
    parsers.parse(
        '我送出 POST /api/v1/auth/user-login 帳號 "{email}" 密碼 "{password}"'
    )
)
def post_user_login(ctx, client, email, password):
    ctx["response"] = client.post(
        "/api/v1/auth/user-login",
        json={"email": email, "password": password},
    )


@when("我以該租戶 ID 送出 POST /api/v1/auth/token")
def post_tenant_token(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/auth/token",
        json={"tenant_id": ctx["tenant_id"]},
    )


@when(
    parsers.parse(
        '我送出 POST /api/v1/auth/login 帳號 "{username}" 密碼 "{password}"'
    )
)
def post_legacy_login(ctx, client, username, password):
    ctx["response"] = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse('回應包含 email 為 "{email}"'))
def check_email(ctx, email):
    body = ctx["response"].json()
    assert body["email"] == email


@then("回應包含 access_token")
def check_access_token(ctx):
    body = ctx["response"].json()
    assert "access_token" in body
    assert len(body["access_token"]) > 0
