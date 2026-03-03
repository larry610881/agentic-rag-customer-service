"""E2E Journey: 知識庫建立→上傳→查詢"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("e2e/knowledge_pipeline.feature")


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


@given("已完成租戶設定")
def setup_tenant(ctx, client):
    resp = client.post("/api/v1/tenants", json={"name": "kb-e2e-tenant"})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]
    ctx["headers"] = {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}


@when(parsers.parse('我建立知識庫 "{name}"'))
def create_kb(ctx, client, name):
    ctx["response"] = client.post(
        "/api/v1/knowledge-bases",
        json={"name": name},
        headers=_auth(ctx["headers"]),
    )
    if ctx["response"].status_code == 201:
        ctx["kb_id"] = ctx["response"].json()["id"]


@when(parsers.parse('我上傳文件 "{filename}" 到該知識庫'))
def upload_document(ctx, client, filename):
    ctx["response"] = client.post(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents",
        files={"file": (filename, b"This is test content for FAQ", "text/plain")},
        headers=_auth(ctx["headers"]),
    )


@when("我查詢該知識庫的文件列表")
def list_documents(ctx, client):
    ctx["response"] = client.get(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents",
        headers=_auth(ctx["headers"]),
    )


@when("我查詢知識庫列表")
def list_kbs(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/knowledge-bases",
        headers=_auth(ctx["headers"]),
    )


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse('知識庫名稱為 "{name}"'))
def check_kb_name(ctx, name):
    body = ctx["response"].json()
    assert body["name"] == name


@then("上傳回應包含 document 和 task_id")
def check_upload(ctx):
    body = ctx["response"].json()
    assert "document" in body
    assert "task_id" in body


@then(parsers.parse("文件列表包含 {count:d} 個文件"))
def check_doc_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count


@then(parsers.parse("知識庫列表包含 {count:d} 個知識庫"))
def check_kb_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count
