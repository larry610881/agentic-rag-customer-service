"""Tenant CRUD Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/tenant/tenant_crud.feature")


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已存在租戶 "{name}"'))
def create_existing_tenant(ctx, client, name):
    resp = client.post("/api/v1/tenants", json={"name": name})
    assert resp.status_code == 201, resp.text
    ctx.setdefault("tenants", {})[name] = resp.json()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('我送出 POST /api/v1/tenants 名稱為 "{name}"'))
def post_create_tenant(ctx, client, name):
    ctx["response"] = client.post("/api/v1/tenants", json={"name": name})


@when("我送出 GET /api/v1/tenants")
def get_tenant_list(ctx, client):
    ctx["response"] = client.get("/api/v1/tenants")


@when("我用該租戶 ID 送出 GET /api/v1/tenants/{id}")
def get_tenant_by_id(ctx, client):
    # Use the first tenant created in Given
    tenant = next(iter(ctx["tenants"].values()))
    ctx["response"] = client.get(f"/api/v1/tenants/{tenant['id']}")


@when("我送出 GET /api/v1/tenants/non-existent-id")
def get_tenant_not_found(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/tenants/00000000-0000-0000-0000-000000000000"
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


@then(parsers.parse('回應包含 name 為 "{name}" 且 plan 為 "{plan}"'))
def check_tenant_fields(ctx, name, plan):
    body = ctx["response"].json()
    assert body["name"] == name
    assert body["plan"] == plan
    assert "id" in body


@then(parsers.parse("回應包含 {count:d} 個租戶"))
def check_tenant_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count


@then(parsers.parse('回應的 name 為 "{name}"'))
def check_tenant_name(ctx, name):
    body = ctx["response"].json()
    assert body["name"] == name
