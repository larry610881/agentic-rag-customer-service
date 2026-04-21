"""Agent Trace Filter + Conversation Grouping — BDD Step Definitions (S-Gov.6a)

驗證 GET /api/v1/observability/agent-traces 的 7 個新 filter +
group_by_conversation 模式。

直接寫 trace 到 DB（避免跑完整 agent pipeline），驗證 endpoint 行為。

注意：observability_router 用 module-level `async_session_factory` 直接連 dev DB，
不走 container DI。我們在 fixture 內 monkeypatch 該變數指向 test DB session
factory，讓 endpoint 真的查 test DB。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infrastructure.db.models.agent_trace_model import (
    AgentExecutionTraceModel,
)

scenarios("integration/admin/agent_trace_filters.feature")


@pytest.fixture(autouse=True)
def _patch_observability_session(app, test_engine, monkeypatch):
    """observability_router 用 module-level async_session_factory（dev DB）。
    為了讓 BDD 測試的 endpoint 查 test DB，把該變數 monkeypatch 成 test
    engine 的 session factory。
    """
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )
    monkeypatch.setattr(
        "src.interfaces.api.observability_router.async_session_factory",
        test_session_factory,
    )
    yield


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("admin 已登入")
def admin_logged_in(ctx, admin_headers):
    ctx["admin_headers"] = admin_headers
    ctx["seeded_traces"] = {}  # name -> trace_id


@given(parsers.parse('已建立租戶 "{tname}"'))
def create_tenant(ctx, client, app, tname):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": tname},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    ctx.setdefault("tenants", {})[tname] = resp.json()["id"]
    ctx["app"] = app


@given(parsers.parse('已建立租戶 "{tname}" 的 bot "{bot_name}"'))
def create_bot(ctx, client, app, tname, bot_name):
    """測試簡化：只記下 bot 名稱對應一個 UUID（不真建 bot row）"""
    ctx.setdefault("bots", {})[bot_name] = str(uuid4())


# ---------------------------------------------------------------------------
# Trace seeding helpers
# ---------------------------------------------------------------------------


def _seed_trace(
    ctx,
    *,
    name: str,
    source: str = "web",
    outcome: str = "success",
    total_ms: float = 100.0,
    user_input: str = "hello",
    conversation_id: str | None = None,
    bot_id: str | None = None,
    agent_mode: str = "react",
):
    """直接 INSERT 一筆 trace。"""
    container = ctx["app"].container
    tenant_id = list(ctx["tenants"].values())[0]
    trace_id = str(uuid4())

    nodes = [
        {
            "type": "user_input",
            "outcome": "success",
            "metadata": {"text": user_input},
        },
        {
            "type": "final_response",
            "outcome": outcome,
            "metadata": {"text": "ok"},
        },
    ]

    async def _insert():
        session = container.db_session()
        try:
            row = AgentExecutionTraceModel(
                id=str(uuid4()),
                trace_id=trace_id,
                tenant_id=tenant_id,
                message_id=None,
                conversation_id=conversation_id,
                agent_mode=agent_mode,
                source=source,
                llm_model="test-model",
                llm_provider="fake",
                bot_id=bot_id,
                nodes=nodes,
                total_ms=total_ms,
                total_tokens={"input": 50, "output": 50, "total": 100},
                outcome=outcome,
                created_at=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()
        finally:
            await session.close()

    _run(_insert())
    ctx["seeded_traces"][name] = trace_id


@given(parsers.parse("已 seed {n:d} 筆 trace："))
def seed_traces_table(ctx, n, datatable):
    """用 BDD datatable seed N 筆 trace。"""
    headers = datatable[0]
    for row in datatable[1:]:
        attrs = dict(zip(headers, row, strict=True))
        kwargs = {"name": attrs["name"]}
        if "source" in attrs:
            kwargs["source"] = attrs["source"]
        if "outcome" in attrs:
            kwargs["outcome"] = attrs["outcome"]
        if "total_ms" in attrs:
            kwargs["total_ms"] = float(attrs["total_ms"])
        _seed_trace(ctx, **kwargs)


@given(parsers.parse("已 seed {n:d} 筆 trace 內含不同 user_input："))
def seed_traces_with_input(ctx, n, datatable):
    headers = datatable[0]
    for row in datatable[1:]:
        attrs = dict(zip(headers, row, strict=True))
        _seed_trace(
            ctx,
            name=attrs["name"],
            user_input=attrs["input_keyword"],
        )


@given(parsers.parse("已 seed 同一 conversation {n:d} 筆 trace"))
def seed_same_conv(ctx, n):
    cid = str(uuid4())
    ctx.setdefault("conv_ids", []).append(cid)
    for i in range(n):
        _seed_trace(
            ctx, name=f"sc_{cid[:4]}_{i}", conversation_id=cid,
        )


@given(parsers.parse("已 seed 另一 conversation {n:d} 筆 trace"))
def seed_another_conv(ctx, n):
    cid = str(uuid4())
    ctx.setdefault("conv_ids", []).append(cid)
    for i in range(n):
        _seed_trace(
            ctx, name=f"ac_{cid[:4]}_{i}", conversation_id=cid,
        )


# ---------------------------------------------------------------------------
# When: HTTP 呼叫
# ---------------------------------------------------------------------------


@when(parsers.re(r"admin 呼叫 GET (?P<url>/api/v1/observability/agent-traces[^\s]*)"))
def admin_get_traces(ctx, client, url):
    resp = client.get(url, headers=ctx["admin_headers"])
    ctx["response"] = resp


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應應包含 {n:d} 筆 trace"))
def verify_trace_count(ctx, n):
    resp = ctx["response"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items", [])
    assert len(items) == n, (
        f"expected {n} traces, got {len(items)}: "
        f"{[i.get('trace_id') for i in items]}"
    )


@then(parsers.parse('該筆 trace 名稱為 "{name}"'))
def verify_single_trace_name(ctx, name):
    body = ctx["response"].json()
    items = body.get("items", [])
    assert len(items) == 1
    expected_id = ctx["seeded_traces"][name]
    assert items[0]["trace_id"] == expected_id


@then(parsers.parse('結果應包含 "{name1}" 與 "{name2}"'))
def verify_two_traces(ctx, name1, name2):
    body = ctx["response"].json()
    trace_ids = {i["trace_id"] for i in body.get("items", [])}
    assert ctx["seeded_traces"][name1] in trace_ids
    assert ctx["seeded_traces"][name2] in trace_ids


@then(parsers.parse("回應應為 grouped 結構含 {n:d} 個 group"))
def verify_grouped_structure(ctx, n):
    body = ctx["response"].json()
    assert body.get("grouped") is True
    assert len(body.get("items", [])) == n


@then(parsers.parse("第一 group 的 trace_count 應為 {n:d}"))
def verify_first_group_count(ctx, n):
    body = ctx["response"].json()
    assert body["items"][0]["trace_count"] == n


@then(parsers.parse("第二 group 的 trace_count 應為 {n:d}"))
def verify_second_group_count(ctx, n):
    body = ctx["response"].json()
    assert body["items"][1]["trace_count"] == n
