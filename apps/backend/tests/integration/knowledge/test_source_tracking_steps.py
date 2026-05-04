"""Source Tracking Integration — DELETE /by-source endpoint.

The integration ``app`` fixture overrides ``container.vector_store`` with an
``AsyncMock`` — these tests assert behavior at the API-contract level
(routing, status codes, tenant isolation, mock-call shape). The actual
Milvus filter-expression / schema behavior is covered by unit tests of
``_build_filter_expr`` and ``_build_schema``.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/knowledge/source_tracking.feature")


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def _parse_quoted_list(quoted: str) -> list[str]:
    """Parse a Gherkin-friendly list literal: '"12345","12346"' → ['12345', '12346']."""
    return [s.strip().strip('"') for s in quoted.split(",")]


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
    # Snapshot the (mock) vector_store so post-action assertions can inspect it.
    ctx["vs_mock"] = app.container.vector_store()


@given(parsers.parse('已登入為租戶 "{name}"'))
def given_tenant_only(ctx, app, create_tenant_login, name):
    ctx["headers"] = create_tenant_login(name)
    ctx["vs_mock"] = app.container.vector_store()


@given(parsers.parse('切換為另一個租戶 "{name}" 重新登入'))
def given_switch_tenant(ctx, create_tenant_login, name):
    # Preserve original kb_id (belongs to first tenant) for cross-tenant attempts.
    ctx["other_tenant_kb_id"] = ctx["kb_id"]
    ctx["headers"] = create_tenant_login(name)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        '我送出 DELETE /by-source 帶 source "{source}" 與 source_ids '
        '[{quoted_ids}]'
    )
)
def when_delete_by_source(ctx, client, source, quoted_ids):
    ids = _parse_quoted_list(quoted_ids)
    ctx["response"] = client.request(
        "DELETE",
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/by-source",
        json={"source": source, "source_ids": ids},
        headers=_auth(ctx["headers"]),
    )


@when(
    parsers.parse(
        '我送出 DELETE /by-source 對 Alpha 的 KB 帶 source "{source}" '
        '與 source_ids [{quoted_ids}]'
    )
)
def when_delete_by_source_cross_tenant(ctx, client, source, quoted_ids):
    ids = _parse_quoted_list(quoted_ids)
    ctx["response"] = client.request(
        "DELETE",
        f"/api/v1/knowledge-bases/{ctx['other_tenant_kb_id']}/documents/by-source",
        json={"source": source, "source_ids": ids},
        headers=_auth(ctx["headers"]),
    )


@when(
    parsers.parse(
        '我送出 DELETE /by-source 對不存在的 KB 帶 source "{source}" '
        '與 source_ids [{quoted_ids}]'
    )
)
def when_delete_by_source_missing_kb(ctx, client, source, quoted_ids):
    ids = _parse_quoted_list(quoted_ids)
    ctx["response"] = client.request(
        "DELETE",
        "/api/v1/knowledge-bases/nonexistent-kb-id/documents/by-source",
        json={"source": source, "source_ids": ids},
        headers=_auth(ctx["headers"]),
    )


@when(
    parsers.parse(
        '我送出 DELETE /by-source 帶 source "{source}" 與空 source_ids 列表'
    )
)
def when_delete_by_source_empty_ids(ctx, client, source):
    ctx["response"] = client.request(
        "DELETE",
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/by-source",
        json={"source": source, "source_ids": []},
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


@then(
    parsers.parse(
        'vector_store.delete 應被呼叫且 filter 為 source "{source}" '
        '與 source_ids [{quoted_ids}]'
    )
)
def then_delete_called_with_filter(ctx, source, quoted_ids):
    expected_ids = _parse_quoted_list(quoted_ids)
    vs = ctx["vs_mock"]
    matching_calls = [
        call for call in vs.delete.call_args_list
        if call.kwargs.get("filters", {}).get("source") == source
    ]
    assert matching_calls, (
        f"vector_store.delete was not called with source={source!r}. "
        f"All calls: {vs.delete.call_args_list}"
    )
    filters = matching_calls[-1].kwargs["filters"]
    assert isinstance(filters.get("source_id"), list), (
        f"Expected source_id to be a list, got {type(filters.get('source_id'))}"
    )
    assert filters["source_id"] == expected_ids, (
        f"Expected source_ids {expected_ids}, got {filters['source_id']}"
    )


@then(
    parsers.parse(
        "vector_store.delete 的 filter source_ids 應為 list 且長度為 {n:d}"
    )
)
def then_delete_filter_source_ids_list_length(ctx, n):
    vs = ctx["vs_mock"]
    assert vs.delete.called, "vector_store.delete was never called"
    last_call = vs.delete.call_args_list[-1]
    filters = last_call.kwargs.get("filters", {})
    assert isinstance(filters.get("source_id"), list), (
        f"Expected source_id to be a list, got {type(filters.get('source_id'))}"
    )
    assert len(filters["source_id"]) == n, (
        f"Expected source_ids length {n}, got {len(filters['source_id'])}"
    )
