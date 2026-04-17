"""Admin Tools API Integration — BDD Step Definitions."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/agent/built_in_tool_admin_api.feature")


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("系統管理員已登入")
def admin_logged_in(ctx, admin_headers):
    ctx["headers"] = admin_headers


@given("一般租戶已登入")
def tenant_logged_in(ctx, auth_headers):
    ctx["headers"] = auth_headers


@given(parsers.parse('租戶 "{tenant_name}" 已登入'))
def named_tenant_logged_in(ctx, create_tenant_login, tenant_name):
    ctx["headers"] = create_tenant_login(tenant_name)


@given(parsers.parse('系統已 seed built-in tool "{name}"'))
def seed_tool(ctx, client, admin_headers, name):
    # Rely on startup lifespan to have already seeded. Defaults = 3 tools.
    resp = client.get("/api/v1/admin/tools", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    names = [t["name"] for t in resp.json()]
    assert name in names, f"expected {name} to be seeded, got {names}"


@given(
    parsers.parse(
        '系統已 seed built-in tool "{name}" 且 scope 為 "{scope}" '
        '白名單為 "{tenant_identifier}"'
    )
)
def seed_tool_with_scope(
    ctx, client, admin_headers, create_tenant_login, name, scope, tenant_identifier
):
    # Create/lookup tenant by name to get real tenant_id
    headers = create_tenant_login(tenant_identifier)
    tenant_id = headers["_tenant_id"]
    # Save for later "登入此租戶" step if needed
    ctx.setdefault("tenant_headers_by_name", {})[tenant_identifier] = headers
    resp = client.put(
        f"/api/v1/admin/tools/{name}",
        json={"scope": scope, "tenant_ids": [tenant_id]},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text


@given(parsers.parse('系統已 seed built-in tool "{name}" 且 scope 為 "{scope}"'))
def seed_tool_global(ctx, client, admin_headers, name, scope):
    resp = client.put(
        f"/api/v1/admin/tools/{name}",
        json={"scope": scope, "tenant_ids": []},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        '我送出 PUT /api/v1/admin/tools/{name} 設 scope 為 "{scope}" '
        '白名單為 "{tenant_name}"'
    )
)
def put_update_scope(ctx, client, create_tenant_login, name, scope, tenant_name):
    tenant_headers = (
        ctx.get("tenant_headers_by_name", {}).get(tenant_name)
        or create_tenant_login(tenant_name)
    )
    tenant_id = tenant_headers["_tenant_id"]
    ctx["response"] = client.put(
        f"/api/v1/admin/tools/{name}",
        json={"scope": scope, "tenant_ids": [tenant_id]},
        headers=ctx["headers"],
    )


@when("我送出 GET /api/v1/admin/tools")
def get_admin_tools(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/admin/tools", headers=ctx["headers"]
    )


@when("我送出 GET /api/v1/agent/built-in-tools")
def get_tenant_built_in_tools(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/agent/built-in-tools", headers=ctx["headers"]
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status_code(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse('回應中 scope 為 "{scope}"'))
def check_response_scope(ctx, scope):
    body = ctx["response"].json()
    assert body["scope"] == scope, body


@then(parsers.parse('回應中 tenant_ids 包含 "{tenant_name}"'))
def check_tenant_ids_contains(ctx, tenant_name):
    body = ctx["response"].json()
    headers = ctx["tenant_headers_by_name"][tenant_name]
    assert headers["_tenant_id"] in body["tenant_ids"], body


@then(parsers.parse('回應不應包含 "{name}"'))
def check_response_not_contains(ctx, name):
    body = ctx["response"].json()
    names = [t["name"] for t in body]
    assert name not in names, names


@then(parsers.parse('回應應包含 "{name}"'))
def check_response_contains(ctx, name):
    body = ctx["response"].json()
    names = [t["name"] for t in body]
    assert name in names, names
