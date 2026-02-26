"""Knowledge Base CRUD Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/knowledge/knowledge_base_crud.feature")


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_tenant_and_login(client, name: str) -> dict:
    """Create a tenant and return auth headers + tenant_id."""
    resp = client.post("/api/v1/tenants", json={"name": name})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]

    return {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}"'))
def login_as_tenant(ctx, client, name):
    headers = _create_tenant_and_login(client, name)
    ctx["headers"] = headers
    ctx["tenant_id"] = headers["_tenant_id"]


@given(parsers.parse('該租戶有知識庫 "{kb_name}"'))
def create_kb_for_current_tenant(ctx, client, kb_name):
    headers = {k: v for k, v in ctx["headers"].items() if not k.startswith("_")}
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    ctx.setdefault("knowledge_bases", []).append(resp.json())


@given(parsers.parse('租戶 "{name}" 有知識庫 "{kb_name}"'))
def create_tenant_with_kb(ctx, client, name, kb_name):
    headers = _create_tenant_and_login(client, name)
    ctx.setdefault("tenant_headers", {})[name] = headers

    auth = {k: v for k, v in headers.items() if not k.startswith("_")}
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    ctx.setdefault("tenant_kbs", {})[name] = resp.json()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('我送出認證 POST /api/v1/knowledge-bases 名稱為 "{kb_name}"'))
def post_create_kb(ctx, client, kb_name):
    headers = {k: v for k, v in ctx["headers"].items() if not k.startswith("_")}
    ctx["response"] = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=headers,
    )


@when(
    parsers.parse('我不帶 token 送出 POST /api/v1/knowledge-bases 名稱為 "{kb_name}"')
)
def post_create_kb_no_auth(ctx, client, kb_name):
    ctx["response"] = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
    )


@when("我送出認證 GET /api/v1/knowledge-bases")
def get_kb_list(ctx, client):
    headers = {k: v for k, v in ctx["headers"].items() if not k.startswith("_")}
    ctx["response"] = client.get("/api/v1/knowledge-bases", headers=headers)


@when(parsers.parse('我以 "{name}" 身分查詢知識庫列表'))
def get_kb_list_as_tenant(ctx, client, name):
    headers = ctx["tenant_headers"][name]
    auth = {k: v for k, v in headers.items() if not k.startswith("_")}
    ctx["response"] = client.get("/api/v1/knowledge-bases", headers=auth)


@when("我帶無效 token 送出 GET /api/v1/knowledge-bases")
def get_kb_list_invalid_token(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/knowledge-bases",
        headers={"Authorization": "Bearer invalid-token-xxx"},
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


@then(parsers.parse('回應包含 name 為 "{name}" 且含 tenant_id'))
def check_kb_fields(ctx, name):
    body = ctx["response"].json()
    assert body["name"] == name
    assert "tenant_id" in body
    assert body["tenant_id"] == ctx["tenant_id"]


@then(parsers.parse("回應包含 {count:d} 個知識庫"))
def check_kb_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count


@then(parsers.parse('回應只包含 "{kb_name}"'))
def check_kb_isolation(ctx, kb_name):
    body = ctx["response"].json()
    names = [kb["name"] for kb in body]
    assert names == [kb_name], f"Expected only [{kb_name}], got {names}"
