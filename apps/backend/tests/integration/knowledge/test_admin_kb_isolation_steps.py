"""S-Gov.3 Admin KB Isolation — Integration BDD Steps."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/knowledge/admin_kb_isolation.feature")


@pytest.fixture
def ctx():
    return {}


@given("系統管理員已登入")
def admin_logged_in(ctx, admin_headers):
    ctx["admin_headers"] = admin_headers


@given("一般租戶已登入")
def tenant_logged_in(ctx, auth_headers):
    ctx["tenant_headers"] = auth_headers


@given(parsers.parse('一般租戶 "{name}" 已建立 KB "{kb_name}"'))
def tenant_create_kb(ctx, client, create_tenant_login, name, kb_name):
    headers = create_tenant_login(name)
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name, "description": ""},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text


@when("系統管理員送出 GET /api/v1/knowledge-bases")
def admin_get_kb(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/knowledge-bases",
        headers=ctx["admin_headers"],
    )


@when("系統管理員送出 GET /api/v1/admin/knowledge-bases")
def admin_get_admin_kb(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/admin/knowledge-bases",
        headers=ctx["admin_headers"],
    )


@when("一般租戶送出 GET /api/v1/admin/knowledge-bases")
def tenant_get_admin_kb(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/admin/knowledge-bases",
        headers=ctx["tenant_headers"],
    )


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, ctx["response"].text


def _extract_names(response):
    data = response.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    return [kb["name"] for kb in items]


@then(parsers.parse('KB 列表不應包含 "{kb_name}"'))
def kb_list_no_contain(ctx, kb_name):
    names = _extract_names(ctx["response"])
    assert kb_name not in names, f"expected {kb_name} not in {names}"


@then(parsers.parse('KB 列表應包含 "{kb_name}"'))
def kb_list_contain(ctx, kb_name):
    names = _extract_names(ctx["response"])
    assert kb_name in names, f"expected {kb_name} in {names}"
