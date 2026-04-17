"""Observability API 權限守衛 — BDD Step Definitions (S-Gov.3)."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as _sql

from src.domain.shared.constants import SYSTEM_TENANT_ID

scenarios("integration/observability/admin_auth_guard.feature")


@pytest.fixture
def ctx():
    return {"tenants": {}, "traces_created": []}


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


def _insert_trace(test_engine, tenant_id: str):
    """Directly INSERT an agent_execution_traces row for the given tenant."""
    import asyncio
    import uuid
    from datetime import datetime, timezone

    async def _do():
        async with test_engine.begin() as conn:
            await conn.execute(
                _sql(
                    "INSERT INTO agent_execution_traces "
                    "(id, tenant_id, conversation_id, agent_mode, nodes, created_at) "
                    "VALUES (:id, :tid, :cid, :mode, :nodes, :ts)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": tenant_id,
                    "cid": str(uuid.uuid4()),
                    "mode": "react",
                    "nodes": "[]",
                    "ts": datetime.now(timezone.utc),
                },
            )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_do())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("admin 已登入")
def admin_logged_in(ctx, client, admin_headers):
    _ensure_system_tenant(client, admin_headers)
    ctx["admin_headers"] = admin_headers


@given(parsers.parse('一般租戶 "{tname}" 已登入'))
def tenant_logged_in(ctx, client, admin_headers, tname):
    if tname not in ctx["tenants"]:
        ctx["tenants"][tname] = _bootstrap_tenant(client, admin_headers, tname)
    ctx["current_headers"] = ctx["tenants"][tname]["headers"]


@given(parsers.parse('租戶 "{tname}" 有 {count:d} 筆 agent trace'))
def tenant_has_traces(ctx, client, admin_headers, test_engine, tname, count):
    if tname not in ctx["tenants"]:
        ctx["tenants"][tname] = _bootstrap_tenant(client, admin_headers, tname)
    for _ in range(count):
        _insert_trace(test_engine, ctx["tenants"][tname]["tenant_id"])


@given(parsers.parse('SYSTEM 租戶有 {count:d} 筆 agent trace'))
def system_has_traces(ctx, client, admin_headers, test_engine, count):
    _ensure_system_tenant(client, admin_headers)
    for _ in range(count):
        _insert_trace(test_engine, SYSTEM_TENANT_ID)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("我不帶 token 呼叫 GET /api/v1/observability/agent-traces")
def call_no_auth(ctx, client):
    ctx["response"] = client.get("/api/v1/observability/agent-traces")


@when(
    parsers.parse(
        '租戶 "{tname}" 呼叫 GET /api/v1/observability/agent-traces 不帶 tenant_id'
    )
)
def tenant_call_traces(ctx, client, tname):
    headers = ctx["tenants"][tname]["headers"]
    ctx["response"] = client.get(
        "/api/v1/observability/agent-traces", headers=headers
    )
    ctx["expected_tenant_id"] = ctx["tenants"][tname]["tenant_id"]


@when(
    parsers.parse(
        'admin 呼叫 GET /api/v1/observability/agent-traces 帶 tenant_id "{tname}"'
    )
)
def admin_call_traces_with_tenant(ctx, client, tname):
    tid = ctx["tenants"][tname]["tenant_id"]
    ctx["response"] = client.get(
        f"/api/v1/observability/agent-traces?tenant_id={tid}",
        headers=ctx["admin_headers"],
    )
    ctx["expected_tenant_id"] = tid


@when("admin 呼叫 GET /api/v1/observability/agent-traces 不帶 tenant_id")
def admin_call_traces_no_tid(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/observability/agent-traces",
        headers=ctx["admin_headers"],
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def status_code_is(ctx, code):
    assert ctx["response"].status_code == code, (
        f"expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text[:200]}"
    )


@then(parsers.parse('回應中只包含 {tname} 的 trace'))
def response_only_contains_tenant(ctx, tname):
    # Strip optional quotes from feature arg
    tname = tname.strip("'\"")
    body = ctx["response"].json()
    items = body.get("items", [])
    expected_tid = ctx["tenants"][tname]["tenant_id"]
    tids = {i.get("tenant_id") for i in items}
    assert tids == {expected_tid} or (not items and expected_tid), (
        f"expected all tenant_id == {expected_tid}, got {tids}"
    )


@then(parsers.parse('回應中包含 {tname} 的 trace'))
def response_contains_tenant(ctx, tname):
    tname = tname.strip("'\"")
    body = ctx["response"].json()
    items = body.get("items", [])
    expected_tid = ctx["tenants"][tname]["tenant_id"]
    tids = [i.get("tenant_id") for i in items]
    assert expected_tid in tids, (
        f"expected {expected_tid} in {tids}"
    )


@then("回應為空")
def response_empty(ctx):
    body = ctx["response"].json()
    items = body.get("items", [])
    assert items == [], f"expected empty, got {len(items)} items"
