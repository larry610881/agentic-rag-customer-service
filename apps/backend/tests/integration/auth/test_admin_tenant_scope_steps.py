"""Admin 一般功能 API 租戶過濾 — BDD Step Definitions (S-Gov.3).

核心主張：admin 呼叫一般功能 API 時，即使帶 bot_id / conversation_id
指向他租戶資源，因 API 已用 admin 自己的 tenant_id（SYSTEM_TENANT_ID）過濾，
結果應為空或 404，不會越權看到/操作其他租戶資料。
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.shared.constants import SYSTEM_TENANT_ID

scenarios("integration/auth/admin_tenant_scope.feature")


@pytest.fixture
def ctx():
    return {"conversations": {}, "bots": {}, "tenants": {}}


def _bootstrap_tenant(client, admin_headers, name: str) -> dict:
    resp = client.post(
        "/api/v1/tenants", json={"name": name}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token_resp = client.post(
        "/api/v1/auth/token", json={"tenant_id": tenant_id}
    )
    assert token_resp.status_code == 200, token_resp.text
    return {
        "tenant_id": tenant_id,
        "headers": {
            "Authorization": f"Bearer {token_resp.json()['access_token']}"
        },
    }


def _ensure_system_tenant(client, admin_headers):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": "系統", "id": SYSTEM_TENANT_ID},
        headers=admin_headers,
    )
    if resp.status_code not in (201, 409):
        raise AssertionError(resp.text)


def _send_chat(client, headers, bot_id: str | None = None) -> dict:
    payload: dict = {"message": "hello"}
    if bot_id:
        payload["bot_id"] = bot_id
    return client.post("/api/v1/agent/chat", json=payload, headers=headers)


def _make_bot(client, headers, name: str) -> str:
    resp = client.post(
        "/api/v1/bots",
        json={"name": name, "description": ""},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("admin 已登入")
def admin_logged_in(ctx, client, admin_headers):
    _ensure_system_tenant(client, admin_headers)
    ctx["admin_headers"] = admin_headers


@given(parsers.parse('系統租戶有 {count:d} 個對話 "{cid}"'))
def system_has_conversation(ctx, client, admin_headers, count, cid):
    resp = _send_chat(client, admin_headers)
    assert resp.status_code == 200, resp.text
    ctx["conversations"][cid] = {
        "id": resp.json()["conversation_id"],
        "tenant_id": SYSTEM_TENANT_ID,
    }


@given(parsers.parse('租戶 "{tname}" 有 {count:d} 個對話 "{cid}"'))
def tenant_has_conversation(ctx, client, admin_headers, tname, count, cid):
    if tname not in ctx["tenants"]:
        ctx["tenants"][tname] = _bootstrap_tenant(client, admin_headers, tname)
    t = ctx["tenants"][tname]
    resp = _send_chat(client, t["headers"])
    assert resp.status_code == 200, resp.text
    ctx["conversations"][cid] = {
        "id": resp.json()["conversation_id"],
        "tenant_id": t["tenant_id"],
    }


@given(parsers.parse('租戶 "{tname}" 有 bot "{bot_alias}" 與對話 "{cid}"'))
def tenant_has_bot_and_conversation(
    ctx, client, admin_headers, tname, bot_alias, cid
):
    if tname not in ctx["tenants"]:
        ctx["tenants"][tname] = _bootstrap_tenant(client, admin_headers, tname)
    t = ctx["tenants"][tname]
    bot_id = _make_bot(client, t["headers"], bot_alias)
    ctx["bots"][bot_alias] = {"id": bot_id, "tenant_id": t["tenant_id"]}
    resp = _send_chat(client, t["headers"], bot_id=bot_id)
    assert resp.status_code == 200, resp.text
    ctx["conversations"][cid] = {
        "id": resp.json()["conversation_id"],
        "tenant_id": t["tenant_id"],
    }


@given(parsers.parse('租戶 "{tname}" 有 bot "{bot_alias}"'))
def tenant_has_bot(ctx, client, admin_headers, tname, bot_alias):
    if tname not in ctx["tenants"]:
        ctx["tenants"][tname] = _bootstrap_tenant(client, admin_headers, tname)
    t = ctx["tenants"][tname]
    bot_id = _make_bot(client, t["headers"], bot_alias)
    ctx["bots"][bot_alias] = {"id": bot_id, "tenant_id": t["tenant_id"]}


@given(parsers.parse('租戶 "{tname}" 有對話 "{cid}"'))
def tenant_has_conv_shortcut(ctx, client, admin_headers, tname, cid):
    tenant_has_conversation(ctx, client, admin_headers, tname, 1, cid)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("admin 呼叫 GET /api/v1/conversations 不帶 bot_id")
def admin_list_convs(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/conversations", headers=ctx["admin_headers"]
    )


@when(
    parsers.parse('admin 呼叫 GET /api/v1/conversations 帶 bot_id "{bot_alias}"')
)
def admin_list_convs_with_bot(ctx, client, bot_alias):
    bot_id = ctx["bots"][bot_alias]["id"]
    ctx["response"] = client.get(
        f"/api/v1/conversations?bot_id={bot_id}",
        headers=ctx["admin_headers"],
    )


@when(
    parsers.parse('admin 呼叫 POST /api/v1/agent/chat 帶 bot_id "{bot_alias}"')
)
def admin_chat_cross_tenant_bot(ctx, client, bot_alias):
    bot_id = ctx["bots"][bot_alias]["id"]
    ctx["response"] = client.post(
        "/api/v1/agent/chat",
        json={"message": "hi", "bot_id": bot_id},
        headers=ctx["admin_headers"],
    )


@when(
    parsers.parse(
        'admin 呼叫 POST /api/v1/feedback 指向 conversation "{cid}"'
    )
)
def admin_feedback_cross_tenant(ctx, client, cid):
    conv_id = ctx["conversations"][cid]["id"]
    ctx["response"] = client.post(
        "/api/v1/feedback",
        json={
            "conversation_id": conv_id,
            "channel": "web",
            "rating": "up",
        },
        headers=ctx["admin_headers"],
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse('結果應只包含 "{cid}"'))
def result_only_contains(ctx, cid):
    body = ctx["response"].json()
    items = body.get("items", [])
    target_id = ctx["conversations"][cid]["id"]
    ids = [i["id"] for i in items]
    assert ids == [target_id], f"expected [{target_id}], got {ids}"


@then("結果應為空")
def result_empty(ctx):
    body = ctx["response"].json()
    items = body.get("items", [])
    assert items == [], f"expected empty, got {items}"


@then("SendMessageCommand 的 tenant_id 應為 SYSTEM_TENANT_ID")
def verify_chat_scope(ctx):
    """移除 override 後：admin 帶 cross-tenant bot_id → use case 收到
    tenant_id=SYSTEM + bot_id=他租戶 → 找不到該 bot → 404/422/403。
    這就是 override 已移除的觀察性證據。"""
    assert ctx["response"].status_code in (
        403,
        404,
        422,
    ), f"expected 4xx (cross-tenant rejected), got {ctx['response'].status_code}: {ctx['response'].text[:200]}"


@then("SubmitFeedbackCommand 的 tenant_id 應為 SYSTEM_TENANT_ID")
def verify_feedback_scope(ctx):
    """移除 override 後：admin 指向 cross-tenant conversation → use case 收到
    tenant_id=SYSTEM + conv_id=他租戶 → 找不到該 conversation → 404/422/403。"""
    assert ctx["response"].status_code in (
        403,
        404,
        422,
    ), f"expected 4xx (cross-tenant rejected), got {ctx['response'].status_code}: {ctx['response'].text[:200]}"
