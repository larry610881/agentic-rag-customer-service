"""Bulk Ingest Integration — BDD Step Definitions.

The integration ``app`` fixture overrides ``container.process_document_use_case``
and ``container.vector_store`` with AsyncMocks. We assert at the API contract
level (response shape, partial failure aggregation, dedup hook fires).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/knowledge/bulk_ingest.feature")


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def _make_items(n: int, *, source: str | None = None) -> list[dict]:
    items = []
    for i in range(n):
        item: dict = {
            "content": f"audit decision body {i}",
            "filename": f"audit-{1000 + i}",
            "metadata": {},
        }
        if source is not None:
            item["metadata"]["source"] = source
            item["metadata"]["source_id"] = str(1000 + i)
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}" 並建立知識庫 "{kb_name}"'))
def given_tenant_and_kb(ctx, client, app, create_tenant_login, name, kb_name):
    headers = create_tenant_login(name)
    ctx["headers"] = headers
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=_auth(headers),
    )
    assert resp.status_code == 201, resp.text
    ctx["kb_id"] = resp.json()["id"]
    ctx["vs_mock"] = app.container.vector_store()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse("我送出 POST /bulk 含 {n:d} 筆 audit_log 條目"))
def when_bulk_post_n_items(ctx, client, n):
    items = _make_items(n, source="audit_log")
    ctx["response"] = client.post(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/bulk",
        json={"documents": items},
        headers=_auth(ctx["headers"]),
    )


@when("我送出 POST /bulk 含 2 筆有效 + 1 筆 empty content")
def when_bulk_post_with_empty(ctx, client):
    items = [
        {"content": "valid 1", "filename": "doc-1", "metadata": {}},
        {"content": "", "filename": "doc-2", "metadata": {}},
        {"content": "valid 3", "filename": "doc-3", "metadata": {}},
    ]
    ctx["response"] = client.post(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/bulk",
        json={"documents": items},
        headers=_auth(ctx["headers"]),
    )


@when(
    parsers.parse(
        '我送出 POST /bulk 含 1 筆 source "{source}" / source_id "{source_id}"'
    )
)
def when_bulk_post_single_with_source(ctx, client, source, source_id):
    items = [
        {
            "content": "first push",
            "filename": "audit-once",
            "metadata": {"source": source, "source_id": source_id},
        }
    ]
    resp = client.post(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/bulk",
        json={"documents": items},
        headers=_auth(ctx["headers"]),
    )
    ctx["response_first"] = resp
    ctx["response"] = resp


@when(
    parsers.parse(
        '再次送出同樣的 POST /bulk 含 1 筆 source "{source}" / source_id '
        '"{source_id}"'
    )
)
def when_bulk_post_resend(ctx, client, source, source_id):
    # Mark when delete was first called BEFORE the second push so we can verify
    # it fires again.
    vs = ctx["vs_mock"]
    ctx["delete_calls_before_second"] = list(vs.delete.call_args_list)

    items = [
        {
            "content": "second push (replacement)",
            "filename": "audit-once",
            "metadata": {"source": source, "source_id": source_id},
        }
    ]
    ctx["response_second"] = client.post(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/bulk",
        json={"documents": items},
        headers=_auth(ctx["headers"]),
    )
    ctx["response"] = ctx["response_second"]


@when(parsers.parse("我送出 POST /bulk 含 {n:d} 筆 documents"))
def when_bulk_post_n_documents(ctx, client, n):
    items = _make_items(n)
    ctx["response"] = client.post(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/bulk",
        json={"documents": items},
        headers=_auth(ctx["headers"]),
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def then_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse("回應 indexed 為 {indexed:d} 且 failed 為 {failed:d}"))
def then_response_indexed_and_failed(ctx, indexed, failed):
    body = ctx["response"].json()
    assert body.get("indexed") == indexed, (
        f"Expected indexed={indexed}, got body: {body}"
    )
    assert body.get("failed") == failed, (
        f"Expected failed={failed}, got body: {body}"
    )


@then(parsers.parse("回應 results 應包含 {count:d} 筆 status=accepted"))
def then_results_accepted_count(ctx, count):
    body = ctx["response"].json()
    accepted = [r for r in body.get("results", []) if r.get("status") == "accepted"]
    assert len(accepted) == count, (
        f"Expected {count} accepted results, got {len(accepted)}: {body}"
    )


@then(parsers.parse('失敗那筆的 error 應包含 "{token}"'))
def then_failed_error_contains(ctx, token):
    body = ctx["response"].json()
    failed = [r for r in body.get("results", []) if r.get("status") == "failed"]
    assert failed, f"No failed results found in: {body}"
    assert any(token in (r.get("error") or "") for r in failed), (
        f"Token {token!r} not found in failed errors: {failed}"
    )


@then("第二次呼叫前應觸發 vector_store.delete 帶 source / source_id filter")
def then_dedup_delete_called(ctx):
    vs = ctx["vs_mock"]
    new_calls = vs.delete.call_args_list[len(ctx["delete_calls_before_second"]):]
    matching = [
        c for c in new_calls
        if c.kwargs.get("filters", {}).get("source") == "audit_log"
    ]
    assert matching, (
        f"Expected vector_store.delete called with source=audit_log "
        f"during second push, got new calls: {new_calls}"
    )


@then("兩次回應 indexed 都為 1")
def then_both_responses_indexed_one(ctx):
    body1 = ctx["response_first"].json()
    body2 = ctx["response_second"].json()
    assert body1.get("indexed") == 1, f"first: {body1}"
    assert body2.get("indexed") == 1, f"second: {body2}"
