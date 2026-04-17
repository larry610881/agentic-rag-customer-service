"""S-Gov.3 Admin Bot Isolation — Integration BDD Steps."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/bot/admin_bot_isolation.feature")


@pytest.fixture
def ctx():
    return {}


@given("系統管理員已登入")
def admin_logged_in(ctx, admin_headers):
    ctx["admin_headers"] = admin_headers


@given("一般租戶已登入")
def tenant_logged_in(ctx, auth_headers):
    ctx["tenant_headers"] = auth_headers


@given(parsers.parse('一般租戶 "{name}" 已建立 Bot "{bot_name}"'))
def tenant_create_bot(ctx, client, create_tenant_login, name, bot_name):
    headers = create_tenant_login(name)
    resp = client.post(
        "/api/v1/bots",
        json={"name": bot_name},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text


@when("系統管理員送出 GET /api/v1/bots")
def admin_get_bots(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/bots",
        headers=ctx["admin_headers"],
    )


@when("系統管理員送出 GET /api/v1/admin/bots")
def admin_get_admin_bots(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/admin/bots",
        headers=ctx["admin_headers"],
    )


@when("一般租戶送出 GET /api/v1/admin/bots")
def tenant_get_admin_bots(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/admin/bots",
        headers=ctx["tenant_headers"],
    )


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, ctx["response"].text


def _extract_names(response):
    data = response.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    return [b["name"] for b in items]


@then(parsers.parse('Bot 列表不應包含 "{bot_name}"'))
def bot_list_no_contain(ctx, bot_name):
    names = _extract_names(ctx["response"])
    assert bot_name not in names, f"expected {bot_name} not in {names}"


@then(parsers.parse('Bot 列表應包含 "{bot_name}"'))
def bot_list_contain(ctx, bot_name):
    names = _extract_names(ctx["response"])
    assert bot_name in names, f"expected {bot_name} in {names}"
