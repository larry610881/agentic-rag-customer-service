"""E2E Journey: 租戶入駐全流程"""

import pytest
from pytest_bdd import parsers, scenarios, then, when

scenarios("e2e/tenant_onboarding.feature")


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


@when(parsers.parse('我建立租戶 "{name}"'))
def create_tenant(ctx, client, name):
    ctx["response"] = client.post("/api/v1/tenants", json={"name": name})
    if ctx["response"].status_code == 201:
        ctx["tenant_id"] = ctx["response"].json()["id"]
        # Get tenant token for subsequent calls
        token_resp = client.post(
            "/api/v1/auth/token",
            json={"tenant_id": ctx["tenant_id"]},
        )
        ctx["tenant_token"] = token_resp.json()["access_token"]
        ctx["headers"] = {"Authorization": f"Bearer {ctx['tenant_token']}"}


@when(parsers.parse('我為該租戶註冊管理員 "{email}" 密碼 "{password}"'))
def register_admin(ctx, client, email, password):
    ctx["response"] = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "tenant_admin",
            "tenant_id": ctx["tenant_id"],
        },
    )


@when(parsers.parse('我以 "{email}" 密碼 "{password}" 登入'))
def login_user(ctx, client, email, password):
    ctx["response"] = client.post(
        "/api/v1/auth/user-login",
        json={"email": email, "password": password},
    )
    if ctx["response"].status_code == 200:
        ctx["user_token"] = ctx["response"].json()["access_token"]


@when(
    parsers.parse(
        '我以租戶身分設定 LLM Provider "{pname}" 顯示名稱 "{display}"'
    )
)
def create_provider(ctx, client, pname, display):
    ctx["response"] = client.post(
        "/api/v1/settings/providers",
        json={
            "provider_type": "llm",
            "provider_name": pname,
            "display_name": display,
            "api_key": "sk-test-e2e-key",
        },
    )


@when("我查詢 Provider 列表")
def list_providers(ctx, client):
    ctx["response"] = client.get("/api/v1/settings/providers")


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then("取得有效的 access_token")
def check_token(ctx):
    body = ctx["response"].json()
    assert "access_token" in body
    assert len(body["access_token"]) > 10


@then(parsers.parse('租戶名稱為 "{name}"'))
def check_tenant_name(ctx, name):
    body = ctx["response"].json()
    assert body["name"] == name


@then("Provider 建立成功")
def check_provider_created(ctx):
    body = ctx["response"].json()
    assert "id" in body
    assert body["has_api_key"] is True


@then(parsers.parse("Provider 列表包含 {count:d} 個項目"))
def check_provider_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count
