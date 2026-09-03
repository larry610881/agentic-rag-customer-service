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
def create_tenant(ctx, client, admin_headers, name):
    resp = client.post(
        "/api/v1/tenants", json={"name": name}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    ctx["tenant_id"] = resp.json()["id"]


@given(
    parsers.parse('已註冊使用者 "{email}" 密碼 "{password}" 關聯該租戶')
)
def register_user(ctx, client, admin_headers, email, password):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_id": ctx["tenant_id"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text


def _tenant_user_headers(app, tenant_id: str, role: str) -> dict[str, str]:
    token = app.container.jwt_service().create_user_token(
        user_id=f"{role}-test", tenant_id=tenant_id, role=role
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


def _post_register(ctx, client, email, password, headers, role="user"):
    ctx["response"] = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "tenant_id": ctx.get("tenant_id"),
        },
        headers=headers,
    )


@when(
    parsers.parse(
        "我以系統管理員送出 POST /api/v1/auth/register "
        '帳號 "{email}" 密碼 "{password}" 關聯該租戶'
    )
)
def post_register_as_admin(ctx, client, admin_headers, email, password):
    _post_register(ctx, client, email, password, admin_headers)


@when(
    parsers.parse(
        "我無憑證送出 POST /api/v1/auth/register "
        '帳號 "{email}" 密碼 "{password}" 關聯該租戶'
    )
)
def post_register_anonymous(ctx, client, email, password):
    _post_register(ctx, client, email, password, {})


@when(
    parsers.parse(
        "我以該租戶一般使用者送出 POST /api/v1/auth/register "
        '帳號 "{email}" 密碼 "{password}" 關聯該租戶'
    )
)
def post_register_as_user(ctx, client, app, email, password):
    headers = _tenant_user_headers(app, ctx["tenant_id"], "user")
    _post_register(ctx, client, email, password, headers)


@when(
    parsers.parse(
        "我以該租戶管理員送出 POST /api/v1/auth/register "
        '角色 "{role}" 帳號 "{email}" 密碼 "{password}"'
    )
)
def post_register_as_tenant_admin(ctx, client, app, role, email, password):
    headers = _tenant_user_headers(app, ctx["tenant_id"], "tenant_admin")
    _post_register(ctx, client, email, password, headers, role=role)


@when(
    parsers.parse(
        '我送出 POST /api/v1/auth/login 帳號 "{account}" 密碼 "{password}"'
    )
)
def post_login(ctx, client, account, password):
    ctx["response"] = client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": password},
    )


@when("我以該租戶 ID 送出 POST /api/v1/auth/token")
def post_tenant_token(ctx, client):
    # Issue #67：舊語意（給 tenant_id 就發票）已移除；本端點只接受 client_credentials
    ctx["response"] = client.post(
        "/api/v1/auth/token",
        json={"tenant_id": ctx["tenant_id"]},
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
