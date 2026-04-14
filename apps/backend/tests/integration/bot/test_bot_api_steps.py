"""Bot API Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/bot/bot_api.feature")


@pytest.fixture
def ctx():
    return {}


def _create_tenant_and_login(create_tenant_login, name: str) -> dict:
    return create_tenant_login(name)


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}"'))
def login_as_tenant(ctx, create_tenant_login, name):
    ctx["headers"] = _create_tenant_and_login(create_tenant_login, name)


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
    items = body.get("items", body) if isinstance(body, dict) else body
    assert len(items) == count


@then("回應包含綁定的知識庫 ID")
def check_kb_binding(ctx):
    body = ctx["response"].json()
    assert ctx["kb"]["id"] in body["knowledge_base_ids"]


# ---------------------------------------------------------------------------
# MCP multi-server scenarios
# ---------------------------------------------------------------------------

_MCP_SERVERS_FIXTURE = [
    {
        "url": "http://localhost:9000/mcp",
        "name": "joyinkitchen",
        "enabled_tools": ["search_products", "search_courses"],
    },
    {
        "url": "http://localhost:9001/mcp",
        "name": "crm",
        "enabled_tools": ["query_orders"],
    },
]


@when("我送出認證 POST /api/v1/bots 含 MCP 設定")
def post_create_bot_with_mcp(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/bots",
        json={
            "name": "MCP Bot",
            "mcp_servers": _MCP_SERVERS_FIXTURE,
        },
        headers=_auth_only(ctx["headers"]),
    )
    # Store bot for subsequent GET
    if ctx["response"].status_code == 201:
        ctx["bot"] = ctx["response"].json()


@when("我用該回應 Bot ID 送出 GET /api/v1/bots/{id}")
def get_bot_from_response(ctx, client):
    bot_id = ctx["bot"]["id"]
    ctx["response"] = client.get(
        f"/api/v1/bots/{bot_id}",
        headers=_auth_only(ctx["headers"]),
    )


@when("我用該 Bot ID 送出 PUT 更新 mcp_servers")
def update_bot_mcp(ctx, client):
    ctx["response"] = client.put(
        f"/api/v1/bots/{ctx['bot']['id']}",
        json={
            "mcp_servers": [
                {
                    "url": "http://localhost:9002/mcp",
                    "name": "new-server",
                    "enabled_tools": ["tool_a"],
                },
            ],
        },
        headers=_auth_only(ctx["headers"]),
    )


@when("我送出認證 POST /api/v1/bots 含完整欄位")
def post_create_bot_full(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/bots",
        json={
            "name": "Full Bot",
            "max_tool_calls": 10,
            "mcp_servers": [
                {
                    "url": "http://localhost:9000/mcp",
                    "name": "test-server",
                    "enabled_tools": ["tool_x"],
                },
            ],
        },
        headers=_auth_only(ctx["headers"]),
    )


@then(parsers.parse("回應包含 mcp_servers 陣列長度為 {count:d}"))
def check_mcp_servers_count(ctx, count):
    body = ctx["response"].json()
    assert "mcp_servers" in body, f"mcp_servers not in response: {body.keys()}"
    assert len(body["mcp_servers"]) == count, (
        f"Expected {count} servers, got {len(body['mcp_servers'])}: "
        f"{body['mcp_servers']}"
    )


@then(parsers.parse('回應 mcp_servers 第 {idx:d} 個 URL 為 "{url}"'))
def check_mcp_server_url(ctx, idx, url):
    servers = ctx["response"].json()["mcp_servers"]
    assert servers[idx - 1]["url"] == url


@then(parsers.parse('回應 mcp_servers 第 {idx:d} 個 name 為 "{name}"'))
def check_mcp_server_name(ctx, idx, name):
    servers = ctx["response"].json()["mcp_servers"]
    assert servers[idx - 1]["name"] == name


@then(parsers.parse('回應 mcp_servers 第 {idx:d} 個 enabled_tools 包含 "{tool}"'))
def check_mcp_server_tool(ctx, idx, tool):
    servers = ctx["response"].json()["mcp_servers"]
    assert tool in servers[idx - 1]["enabled_tools"]


@then(parsers.parse('回應欄位 {field} 為 "{value}"'))
def check_field_str(ctx, field, value):
    body = ctx["response"].json()
    assert str(body[field]) == value, (
        f"Expected {field}={value}, got {body[field]}"
    )


@then(parsers.parse("回應欄位 {field} 為 {value:d}"))
def check_field_int(ctx, field, value):
    body = ctx["response"].json()
    assert body[field] == value, (
        f"Expected {field}={value}, got {body[field]}"
    )
