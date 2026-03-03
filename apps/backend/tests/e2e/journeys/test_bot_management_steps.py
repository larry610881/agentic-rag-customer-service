"""E2E Journey: Bot 管理完整流程"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("e2e/bot_management.feature")


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


@given("已完成租戶設定並建立知識庫")
def setup_tenant_and_kb(ctx, client):
    # Create tenant + token
    resp = client.post("/api/v1/tenants", json={"name": "bot-e2e-tenant"})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    token = token_resp.json()["access_token"]
    ctx["headers"] = {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}

    # Create KB
    kb_resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Bot FAQ"},
        headers=_auth(ctx["headers"]),
    )
    assert kb_resp.status_code == 201, kb_resp.text
    ctx["kb_id"] = kb_resp.json()["id"]


@when(parsers.parse('我建立 Bot "{name}" 綁定知識庫'))
def create_bot(ctx, client, name):
    ctx["response"] = client.post(
        "/api/v1/bots",
        json={"name": name, "knowledge_base_ids": [ctx["kb_id"]]},
        headers=_auth(ctx["headers"]),
    )
    if ctx["response"].status_code == 201:
        ctx["bot_id"] = ctx["response"].json()["id"]


@when("我查詢 Bot 列表")
def list_bots(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/bots",
        headers=_auth(ctx["headers"]),
    )


@when(parsers.parse('我更新 Bot 名稱為 "{name}"'))
def update_bot(ctx, client, name):
    ctx["response"] = client.put(
        f"/api/v1/bots/{ctx['bot_id']}",
        json={"name": name},
        headers=_auth(ctx["headers"]),
    )


@when("我查詢該 Bot 詳情")
def get_bot(ctx, client):
    ctx["response"] = client.get(
        f"/api/v1/bots/{ctx['bot_id']}",
        headers=_auth(ctx["headers"]),
    )


@when("我刪除該 Bot")
def delete_bot(ctx, client):
    ctx["response"] = client.delete(
        f"/api/v1/bots/{ctx['bot_id']}",
        headers=_auth(ctx["headers"]),
    )


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse('Bot 名稱為 "{name}"'))
def check_bot_name(ctx, name):
    assert ctx["response"].json()["name"] == name


@then("Bot 已綁定知識庫")
def check_kb_bound(ctx):
    assert ctx["kb_id"] in ctx["response"].json()["knowledge_base_ids"]


@then(parsers.parse("Bot 列表包含 {count:d} 個 Bot"))
def check_bot_count(ctx, count):
    assert len(ctx["response"].json()) == count
