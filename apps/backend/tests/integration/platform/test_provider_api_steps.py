"""Provider Settings API Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/platform/provider_api.feature")


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(
    parsers.parse('已建立 Provider "{ptype}" "{pname}" "{display}"')
)
def create_provider(ctx, client, admin_headers, ptype, pname, display):
    resp = client.post(
        "/api/v1/settings/providers",
        json={
            "provider_type": ptype,
            "provider_name": pname,
            "display_name": display,
            "api_key": "sk-test-key-12345",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    ctx["provider"] = resp.json()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        '我送出 POST /api/v1/settings/providers 類型 "{ptype}" '
        '名稱 "{pname}" 顯示名稱 "{display}"'
    )
)
def post_create_provider(ctx, client, admin_headers, ptype, pname, display):
    ctx["response"] = client.post(
        "/api/v1/settings/providers",
        json={
            "provider_type": ptype,
            "provider_name": pname,
            "display_name": display,
            "api_key": "sk-test-key-12345",
        },
        headers=admin_headers,
    )


@when("我無憑證送出 GET /api/v1/settings/providers")
def get_provider_list_anonymous(ctx, client):
    ctx["response"] = client.get("/api/v1/settings/providers")


@when(
    parsers.parse(
        '我以租戶管理員送出 POST /api/v1/settings/providers 類型 "{ptype}" '
        '名稱 "{pname}" 顯示名稱 "{display}"'
    )
)
def post_create_provider_as_tenant_admin(ctx, client, app, ptype, pname, display):
    token = app.container.jwt_service().create_user_token(
        user_id="ta-test", tenant_id="tenant-x", role="tenant_admin"
    )
    ctx["response"] = client.post(
        "/api/v1/settings/providers",
        json={
            "provider_type": ptype,
            "provider_name": pname,
            "display_name": display,
            "api_key": "sk-test-key-12345",
        },
        headers={"Authorization": f"Bearer {token}"},
    )


@when("我送出 GET /api/v1/settings/providers")
def get_provider_list(ctx, client, admin_headers):
    ctx["response"] = client.get(
        "/api/v1/settings/providers", headers=admin_headers
    )


@when("我送出 GET /api/v1/settings/providers?type=llm")
def get_provider_list_by_type(ctx, client, admin_headers):
    ctx["response"] = client.get(
        "/api/v1/settings/providers?type=llm", headers=admin_headers
    )


@when(parsers.parse("我送出 GET /api/v1/settings/providers/{provider_id}"))
def get_provider_not_found(ctx, client, admin_headers, provider_id):
    ctx["response"] = client.get(
        f"/api/v1/settings/providers/{provider_id}", headers=admin_headers
    )


@when("我用該 Provider ID 送出 GET /api/v1/settings/providers/{id}")
def get_provider_by_id(ctx, client, admin_headers):
    ctx["response"] = client.get(
        f"/api/v1/settings/providers/{ctx['provider']['id']}",
        headers=admin_headers,
    )


@when(
    parsers.parse(
        '我用該 Provider ID 送出 PUT /api/v1/settings/providers/{{id}} '
        '顯示名稱 "{display}"'
    )
)
def update_provider(ctx, client, admin_headers, display):
    ctx["response"] = client.put(
        f"/api/v1/settings/providers/{ctx['provider']['id']}",
        json={"display_name": display},
        headers=admin_headers,
    )


@when("我用該 Provider ID 送出 DELETE /api/v1/settings/providers/{id}")
def delete_provider(ctx, client, admin_headers):
    ctx["response"] = client.delete(
        f"/api/v1/settings/providers/{ctx['provider']['id']}",
        headers=admin_headers,
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


@then(parsers.parse('回應包含 provider_name 為 "{name}"'))
def check_provider_name(ctx, name):
    body = ctx["response"].json()
    assert body["provider_name"] == name


@then(parsers.parse('回應包含 display_name 為 "{name}"'))
def check_display_name(ctx, name):
    body = ctx["response"].json()
    assert body["display_name"] == name


@then(parsers.parse("回應包含 has_api_key 為 true"))
def check_has_api_key(ctx):
    body = ctx["response"].json()
    assert body["has_api_key"] is True


@then(parsers.parse("回應包含 {count:d} 個 Provider"))
def check_provider_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count
