"""Bot API Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/bot/bot_api.feature")


@pytest.fixture
def ctx():
    return {}


def _create_tenant_and_login(client, name: str) -> dict:
    resp = client.post("/api/v1/tenants", json={"name": name})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}"'))
def login_as_tenant(ctx, client, name):
    ctx["headers"] = _create_tenant_and_login(client, name)


@given(parsers.parse('已建立 Bot "{name}"'))
def create_bot(ctx, client, name):
    resp = client.post(
        "/api/v1/bots",
        json={"name": name},
        headers=_auth_only(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text
    ctx["bot"] = resp.json()


@given(parsers.parse('已建立知識庫 "{kb_name}"'))
def create_kb(ctx, client, kb_name):
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=_auth_only(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text
    ctx["kb"] = resp.json()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('我送出認證 POST /api/v1/bots 名稱為 "{name}"'))
def post_create_bot(ctx, client, name):
    ctx["response"] = client.post(
        "/api/v1/bots",
        json={"name": name},
        headers=_auth_only(ctx["headers"]),
    )


@when(parsers.parse('我送出認證 POST /api/v1/bots 名稱為 "{name}" 綁定知識庫'))
def post_create_bot_with_kb(ctx, client, name):
    ctx["response"] = client.post(
        "/api/v1/bots",
        json={"name": name, "knowledge_base_ids": [ctx["kb"]["id"]]},
        headers=_auth_only(ctx["headers"]),
    )


@when("我送出認證 GET /api/v1/bots")
def get_bot_list(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/bots", headers=_auth_only(ctx["headers"])
    )


@when(parsers.parse("我送出認證 GET /api/v1/bots/{bot_id}"))
def get_bot_not_found(ctx, client, bot_id):
    ctx["response"] = client.get(
        f"/api/v1/bots/{bot_id}", headers=_auth_only(ctx["headers"])
    )


@when("我用該 Bot ID 送出 GET /api/v1/bots/{id}")
def get_bot_by_id(ctx, client):
    ctx["response"] = client.get(
        f"/api/v1/bots/{ctx['bot']['id']}",
        headers=_auth_only(ctx["headers"]),
    )


@when(parsers.parse('我用該 Bot ID 送出 PUT /api/v1/bots/{{id}} 名稱為 "{name}"'))
def update_bot(ctx, client, name):
    ctx["response"] = client.put(
        f"/api/v1/bots/{ctx['bot']['id']}",
        json={"name": name},
        headers=_auth_only(ctx["headers"]),
    )


@when("我用該 Bot ID 送出 DELETE /api/v1/bots/{id}")
def delete_bot(ctx, client):
    ctx["response"] = client.delete(
        f"/api/v1/bots/{ctx['bot']['id']}",
        headers=_auth_only(ctx["headers"]),
    )


@when("我不帶 token 送出 GET /api/v1/bots")
def get_bots_no_auth(ctx, client):
    ctx["response"] = client.get("/api/v1/bots")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse('回應包含 bot name 為 "{name}"'))
def check_bot_name(ctx, name):
    body = ctx["response"].json()
    assert body["name"] == name


@then(parsers.parse("回應包含 {count:d} 個 Bot"))
def check_bot_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count


@then("回應包含綁定的知識庫 ID")
def check_kb_binding(ctx):
    body = ctx["response"].json()
    assert ctx["kb"]["id"] in body["knowledge_base_ids"]
