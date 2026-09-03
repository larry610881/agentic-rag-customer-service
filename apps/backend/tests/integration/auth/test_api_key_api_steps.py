"""租戶 API key 端到端 — BDD Step Definitions（Issue #67 P2，真實 DB）。"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/auth/api_key_api.feature")


@pytest.fixture
def ctx():
    return {}


def _admin_of(client, tenant_id: str) -> dict[str, str]:
    token = client._app.container.jwt_service().create_user_token(
        user_id=f"admin-{tenant_id[:8]}", tenant_id=tenant_id, role="tenant_admin"
    )
    return {"Authorization": f"Bearer {token}"}


def _create_tenant(client, admin_headers, name: str) -> str:
    resp = client.post("/api/v1/tenants", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@given(parsers.parse('已存在租戶 "{name}" 與其租戶管理員'))
def tenant_with_admin(ctx, client, admin_headers, name):
    ctx["tenant_id"] = _create_tenant(client, admin_headers, name)
    ctx["headers"] = _admin_of(client, ctx["tenant_id"])


@when(parsers.parse('租戶管理員建立 API key 名稱 "{name}" scopes "{scopes}"'))
def create_key(ctx, client, name, scopes):
    ctx["response"] = client.post(
        "/api/v1/api-keys",
        json={"name": name, "scopes": scopes.split()},
        headers=ctx["headers"],
    )
    if ctx["response"].status_code == 201:
        body = ctx["response"].json()
        ctx["key"] = body
        ctx["client_secret"] = body["client_secret"]


@when("以該 key 換票")
def exchange(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/auth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": ctx["key"]["client_id"],
            "client_secret": ctx["client_secret"],
        },
    )
    if ctx["response"].status_code == 200:
        ctx["api_headers"] = {
            "Authorization": f"Bearer {ctx['response'].json()['access_token']}"
        }


@when(parsers.parse("以機器票送出 GET {path}"))
def api_get(ctx, client, path):
    ctx["response"] = client.get(path, headers=ctx["api_headers"])


@when("租戶管理員撤銷該 key")
def revoke(ctx, client):
    ctx["response"] = client.delete(
        f"/api/v1/api-keys/{ctx['key']['id']}", headers=ctx["headers"]
    )


@when(parsers.parse('另一租戶 "{name}" 的管理員列出 API key'))
def other_lists(ctx, client, admin_headers, name):
    other = _create_tenant(client, admin_headers, name)
    ctx["other_headers"] = _admin_of(client, other)
    ctx["response"] = client.get("/api/v1/api-keys", headers=ctx["other_headers"])


@when(parsers.parse('另一租戶 "{name}" 的管理員撤銷該 key'))
def other_revokes(ctx, client, admin_headers, name):
    if "other_headers" not in ctx:
        other = _create_tenant(client, admin_headers, name)
        ctx["other_headers"] = _admin_of(client, other)
    ctx["response"] = client.delete(
        f"/api/v1/api-keys/{ctx['key']['id']}", headers=ctx["other_headers"]
    )


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: {ctx['response'].text}"
    )


@then("建立回應含一次性 client_secret")
def has_secret(ctx):
    assert ctx["client_secret"].startswith("ark_")


@then("列表不含該 key")
def list_excludes(ctx):
    ids = [k["id"] for k in ctx["response"].json()]
    assert ctx["key"]["id"] not in ids
