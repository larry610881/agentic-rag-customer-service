"""Unified Search Integration — BDD Step Definitions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.rag.value_objects import SearchResult

scenarios("integration/rag/unified_search.feature")


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def _make_search_mock(default_score: float = 0.85) -> AsyncMock:
    """Mock vector_store.search returning one canned hit per call.

    Hits include source/source_id so unified search response shape is testable
    without spinning up Milvus.
    """

    async def _search(*args, **kwargs):
        collection = kwargs.get("collection") or (args[0] if args else "kb_unknown")
        return [
            SearchResult(
                id=f"chunk-{collection}-1",
                score=default_score,
                payload={
                    "tenant_id": kwargs.get("filters", {}).get("tenant_id", ""),
                    "document_id": "doc-1",
                    "content": "decision body",
                    "source": kwargs.get("filters", {}).get("source", "audit_log"),
                    "source_id": "12345",
                    "kb_id": collection.replace("kb_", ""),
                },
            )
        ]

    mock = AsyncMock(side_effect=_search)
    return mock


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        '已登入為租戶 "{name}" 並建立兩個知識庫 "{kb1}" 與 "{kb2}"'
    )
)
def given_two_kbs(ctx, client, app, create_tenant_login, name, kb1, kb2):
    headers = create_tenant_login(name)
    ctx["headers"] = headers
    ctx["kb_ids"] = []
    for kb_name in (kb1, kb2):
        resp = client.post(
            "/api/v1/knowledge-bases",
            json={"name": kb_name},
            headers=_auth(headers),
        )
        assert resp.status_code == 201, resp.text
        ctx["kb_ids"].append(resp.json()["id"])

    # Replace vector_store with a side-effect-driven mock so we can return
    # at least one hit per collection (the default AsyncMock returns
    # MagicMock objects which break SearchResult iteration).
    container = app.container
    vs_mock = container.vector_store()
    vs_mock.search = _make_search_mock()
    ctx["vs_mock"] = vs_mock
    ctx["embedding_mock"] = container.embedding_service()


@given(parsers.parse('已登入為租戶 "{name}" 並建立知識庫 "{kb_name}"'))
def given_one_kb(ctx, client, app, create_tenant_login, name, kb_name):
    headers = create_tenant_login(name)
    ctx["headers"] = headers
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=_auth(headers),
    )
    assert resp.status_code == 201, resp.text
    ctx["kb_ids"] = [resp.json()["id"]]
    ctx["vs_mock"] = app.container.vector_store()


@given(parsers.parse('切換為另一個租戶 "{name}" 重新登入'))
def given_switch_tenant(ctx, create_tenant_login, name):
    ctx["other_tenant_kb_ids"] = ctx["kb_ids"]
    ctx["headers"] = create_tenant_login(name)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("我送出 POST /api/v1/rag/search 含 query 與兩個 kb_ids")
def when_unified_search_two_kbs(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/rag/search",
        json={
            "query": "客戶提類似 CR 怎麼決定的",
            "kb_ids": ctx["kb_ids"],
            "retrieval_modes": ["raw"],
            "top_k": 5,
        },
        headers=_auth(ctx["headers"]),
    )


@when(parsers.parse('我送出 POST /api/v1/rag/search 含 source filter "{source}"'))
def when_unified_search_with_source(ctx, client, source):
    ctx["response"] = client.post(
        "/api/v1/rag/search",
        json={
            "query": "歷史決議",
            "kb_ids": ctx["kb_ids"],
            "retrieval_modes": ["raw"],
            "filters": {"source": source},
            "top_k": 5,
        },
        headers=_auth(ctx["headers"]),
    )


@when("我送出 POST /api/v1/rag/search 對 Alpha 的 KB")
def when_unified_search_cross_tenant(ctx, client):
    ctx["response"] = client.post(
        "/api/v1/rag/search",
        json={
            "query": "anything",
            "kb_ids": ctx["other_tenant_kb_ids"],
            "retrieval_modes": ["raw"],
            "top_k": 5,
        },
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


@then("回應包含 results 陣列且每筆有 kb_id")
def then_results_have_kb_id(ctx):
    body = ctx["response"].json()
    assert "results" in body, body
    assert len(body["results"]) >= 1, body
    for r in body["results"]:
        assert r.get("kb_id"), f"missing kb_id in result: {r}"


@then("vector_store.search 應對兩個 collection 都被呼叫")
def then_search_called_for_both_collections(ctx):
    vs = ctx["vs_mock"]
    called_collections = {
        c.kwargs.get("collection") for c in vs.search.call_args_list
    }
    expected = {f"kb_{kid}" for kid in ctx["kb_ids"]}
    assert expected.issubset(called_collections), (
        f"Expected search on {expected}, actually called: {called_collections}"
    )


@then("vector_store.search 的 filter 應同時帶 tenant_id 與 source")
def then_filter_has_tenant_and_source(ctx):
    vs = ctx["vs_mock"]
    matching = [
        c for c in vs.search.call_args_list
        if (c.kwargs.get("filters") or {}).get("source") == "audit_log"
    ]
    assert matching, (
        f"No search call had source=audit_log filter: "
        f"{[c.kwargs.get('filters') for c in vs.search.call_args_list]}"
    )
    for c in matching:
        filters = c.kwargs["filters"]
        assert filters.get("tenant_id"), (
            f"Expected tenant_id in filter alongside source: {filters}"
        )
