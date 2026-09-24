"""Bulk Ingest Integration — BDD Step Definitions.

The integration ``app`` fixture overrides ``container.process_document_use_case``
and ``container.vector_store`` with AsyncMocks. We assert at the API contract
level (response shape, partial failure aggregation, dedup hook fires).

Since 5e80c3f (Outbox Phase C) the dedup sweep writes a ``vector.delete``
outbox event instead of calling ``vector_store.delete`` inline; the dedup
scenario runs the real ``DrainOutboxUseCase`` once after each push (what the
worker's ``drain_outbox`` cron does) before asserting on ``vector_store.delete``.

#469963: dedup deletes by document id. The race scenario gives the mocked
``vector_store.delete`` an in-memory store that applies filters the way
``MilvusVectorStore._build_filter_expr`` does (AND of keys; list → IN), so the
"new version processed before drain" ordering is observable.
"""

from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.integration.conftest import TEST_DB_URL, run_outside_request

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


@given("向量庫依 filter 實際刪除資料")
def given_vector_store_applies_filters(ctx):
    ctx["vectors"] = []

    def _matches(row: dict, filters: dict) -> bool:
        for k, v in filters.items():
            if isinstance(v, list):
                if row.get(k) not in v:
                    return False
            elif row.get(k) != v:
                return False
        return True

    async def _delete(collection, filters, **_kw):
        ctx["vectors"][:] = [
            r for r in ctx["vectors"]
            if not (r["collection"] == collection and _matches(r, filters))
        ]

    ctx["vs_mock"].delete.side_effect = _delete


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


@when("上一筆上傳的文件處理完成並寫入向量")
def when_last_upload_processed(ctx):
    """模擬 worker process_document 完成：新文件 chunks 進向量庫（帶 source 欄位）。"""
    (item,) = ctx["response"].json()["results"]
    ctx["vectors"].append(
        {
            "collection": f"kb_{ctx['kb_id']}",
            "document_id": item["document_id"],
            "tenant_id": ctx["headers"]["_tenant_id"],
            "source": "audit_log",
            "source_id": "12345",
        }
    )


@when("outbox drain 排程執行一次")
def when_drain_outbox(ctx, app):
    # 與 worker.drain_outbox_task 相同的 use case；handlers 綁定的是被
    # integration app fixture 覆寫成 AsyncMock 的 vector_store。
    run_outside_request(lambda: app.container.drain_outbox_use_case().execute())


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


def _doc_id(resp) -> str:
    (item,) = resp.json()["results"]
    return item["document_id"]


@then("第二次推送應觸發 vector_store.delete 帶第一次文件的 document_id filter")
def then_dedup_delete_called(ctx):
    vs = ctx["vs_mock"]
    new_calls = vs.delete.call_args_list[len(ctx["delete_calls_before_second"]):]
    first_id = _doc_id(ctx["response_first"])
    filters = [c.kwargs.get("filters", {}) for c in new_calls]
    assert filters == [{"document_id": [first_id]}], (
        f"dedup 應只以舊文件 id 刪除（不可用 source/source_id 過濾），got: {filters}"
    )


@then("向量庫只剩第二次上傳文件的向量")
def then_only_second_vectors_remain(ctx):
    remaining = [r["document_id"] for r in ctx["vectors"]]
    assert remaining == [_doc_id(ctx["response_second"])], remaining


@then("該 source_id 在 PG 只剩第二次上傳的文件")
def then_pg_only_second_document(ctx):
    async def _ids():
        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        try:
            async with eng.connect() as conn:
                rows = await conn.execute(
                    text(
                        "SELECT id FROM documents WHERE kb_id = :kb "
                        "AND source = 'audit_log' AND source_id = '12345'"
                    ),
                    {"kb": ctx["kb_id"]},
                )
                return [r[0] for r in rows]
        finally:
            await eng.dispose()

    loop = asyncio.new_event_loop()
    try:
        ids = loop.run_until_complete(_ids())
    finally:
        loop.close()
    assert ids == [_doc_id(ctx["response_second"])], ids


@then("兩次回應 indexed 都為 1")
def then_both_responses_indexed_one(ctx):
    body1 = ctx["response_first"].json()
    body2 = ctx["response_second"].json()
    assert body1.get("indexed") == 1, f"first: {body1}"
    assert body2.get("indexed") == 1, f"second: {body2}"
