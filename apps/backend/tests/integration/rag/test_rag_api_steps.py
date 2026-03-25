"""RAG API Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/rag/rag_api.feature")


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


@when("我送出 RAG 查詢到不存在的知識庫")
def post_rag_query_not_found(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": "00000000-0000-0000-0000-000000000000",
            "query": "測試查詢",
        },
        headers=_auth_only(ctx["headers"]),
    )


@when("我不帶 token 送出 POST /api/v1/rag/query")
def post_rag_no_auth(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/rag/query",
        json={"knowledge_base_id": "any", "query": "test"},
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )
