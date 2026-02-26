"""Document CRUD Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/knowledge/document_crud.feature")


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client, tenant_name: str) -> dict:
    """Create tenant + get JWT → return full context dict."""
    resp = client.post("/api/v1/tenants", json={"name": tenant_name})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}


def _auth(headers: dict) -> dict:
    """Strip internal keys from headers dict."""
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def _upload_file(client, kb_id: str, filename: str, headers: dict):
    """Upload a text file to a knowledge base."""
    content_type = "text/plain"
    if filename.endswith(".exe"):
        content_type = "application/octet-stream"

    return client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": (filename, b"hello world", content_type)},
        headers=_auth(headers),
    )


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}" 並建立知識庫 "{kb_name}"'))
def setup_tenant_and_kb(ctx, client, name, kb_name):
    headers = _login(client, name)
    ctx["headers"] = headers

    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=_auth(headers),
    )
    assert resp.status_code == 201, resp.text
    ctx["kb_id"] = resp.json()["id"]


@given(parsers.parse('該知識庫已有文件 "{filename}"'))
def upload_existing_file(ctx, client, filename):
    resp = _upload_file(client, ctx["kb_id"], filename, ctx["headers"])
    assert resp.status_code == 201, resp.text
    ctx.setdefault("documents", []).append(resp.json()["document"])


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('我上傳檔案 "{filename}" 到該知識庫'))
def upload_file(ctx, client, filename):
    ctx["response"] = _upload_file(client, ctx["kb_id"], filename, ctx["headers"])


@when("我送出認證 GET 文件列表")
def get_document_list(ctx, client):
    ctx["response"] = client.get(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents",
        headers=_auth(ctx["headers"]),
    )


@when("我刪除該文件")
def delete_document(ctx, client):
    doc_id = ctx["documents"][0]["id"]
    ctx["response"] = client.delete(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/{doc_id}",
        headers=_auth(ctx["headers"]),
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


@then("回應包含 document id 和 task_id")
def check_upload_response(ctx):
    body = ctx["response"].json()
    assert "document" in body
    assert "id" in body["document"]
    assert "task_id" in body


@then(parsers.parse("回應包含 {count:d} 個文件"))
def check_document_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count


@then("再查詢文件列表為空")
def verify_empty_after_delete(ctx, client):
    resp = client.get(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents",
        headers=_auth(ctx["headers"]),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0
