"""Bot Studio Phase 1 Integration — BDD Step Definitions.

Validates Phase 1 contracts:
1. Stream events 帶 node_id → 對應 trace.nodes
2. 多 worker → SSE 收到 worker_routing event
3. 失敗路徑 → trace 含 outcome=failed 節點 + error_message
4. 既有 web 通路 (identity_source 不帶) → trace.source = "web" + 所有節點 outcome = "success"
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from dependency_injector import providers
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.agent.services import AgentService
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

scenarios("integration/agent/bot_studio_phase1.feature")


class _StudioFakeAgent(AgentService):
    """Fake agent — start trace, yield token, add tool/final nodes.
    Mimic 真實 react_agent_service 的 worker_routing event yield 行為，
    讓 multi-worker BDD 場景能驗證 SSE event 序列化。
    """

    async def process_message(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def process_message_stream(
        self, tenant_id: str, *args: Any, **kwargs: Any
    ):  # type: ignore[override]
        AgentTraceCollector.start(tenant_id, "react")
        AgentTraceCollector.add_node(
            "user_input", "user input", None, 0.0, 0.0,
        )

        # Mimic real react_agent_service: yield worker_routing if metadata 有
        metadata = kwargs.get("metadata") or {}
        wr_info = metadata.get("_worker_routing")
        if isinstance(wr_info, dict) and wr_info.get("name"):
            AgentTraceCollector.add_node(
                "worker_routing",
                f"已分流至 Worker：{wr_info['name']}",
                None, 0.5, 0.5,
                worker_name=wr_info["name"],
                worker_llm=wr_info.get("llm_model") or "(default)",
                worker_kb_count=wr_info.get("kb_count", 0),
            )
            yield {
                "type": "worker_routing",
                "worker_name": wr_info["name"],
                "worker_llm": wr_info.get("llm_model") or "(default)",
                "node_id": AgentTraceCollector.last_node_id(),
                "ts_ms": round(AgentTraceCollector.offset_ms(), 1),
            }

        AgentTraceCollector.add_node(
            "tool_call", "rag_query", None, 1.0, 5.0,
        )
        yield {
            "type": "token",
            "content": "ok",
            "node_id": AgentTraceCollector.last_node_id(),
            "ts_ms": round(AgentTraceCollector.offset_ms(), 1),
        }
        AgentTraceCollector.add_node(
            "final_response", "最終回覆", None, 6.0, 6.0,
        )


class _FailingFakeAgent(AgentService):
    """Fake agent — start trace, raise exception to test failed-node path."""

    async def process_message(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def process_message_stream(
        self, tenant_id: str, *args: Any, **kwargs: Any
    ):  # type: ignore[override]
        AgentTraceCollector.start(tenant_id, "react")
        AgentTraceCollector.add_node(
            "user_input", "user input", None, 0.0, 0.0,
        )
        AgentTraceCollector.add_node(
            "agent_llm", "LLM call", None, 1.0, 1.0,
        )
        # 模擬 LLM 呼叫失敗 → mark current node failed
        yield {"type": "status", "status": "react_thinking"}
        raise RuntimeError("simulated LLM failure")


@pytest.fixture
def ctx():
    return {}


@pytest.fixture
def fake_agent_factory():
    """選擇要注入哪一種 fake agent (預設 success)。"""
    return {"cls": _StudioFakeAgent}


class _FixedClassifier:
    """Always pick the first worker — bypasses LLM-dependent classification
    so multi-worker BDD scenarios can deterministically validate the
    worker_routing event flow."""

    async def classify_workers(
        self, *, user_message, router_context, workers, router_model
    ):
        return workers[0] if workers else None


@pytest.fixture(autouse=True)
def _override_di(app, test_engine, fake_agent_factory):
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    app.container.agent_service.override(
        providers.Singleton(fake_agent_factory["cls"])
    )
    app.container.trace_session_factory.override(
        providers.Object(test_session_factory)
    )
    app.container.intent_classifier.override(
        providers.Singleton(_FixedClassifier)
    )
    yield
    app.container.agent_service.reset_override()
    app.container.trace_session_factory.reset_override()
    app.container.intent_classifier.reset_override()


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def _post_stream(client, ctx, payload):
    resp = client.post(
        "/api/v1/agent/chat/stream",
        json=payload,
        headers=_auth_only(ctx["headers"]),
    )
    events = []
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    ctx["sse_events"] = events
    done = next((e for e in events if e.get("type") == "done"), None)
    if done and "trace_id" in done:
        ctx["trace_id"] = done["trace_id"]


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("一般租戶已登入")
def tenant_logged_in(ctx, auth_headers):
    ctx["headers"] = auth_headers


@given("該租戶已建立一個 bot")
def create_bot(ctx, client):
    resp = client.post(
        "/api/v1/bots",
        json={"name": "phase1-bot"},
        headers=_auth_only(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text
    ctx["bot"] = resp.json()


@given(
    parsers.parse(
        '該租戶已建立一個 bot 且綁定 2 個 worker "{w1}" 與 "{w2}"'
    )
)
def create_bot_with_workers(ctx, client, w1, w2):
    resp = client.post(
        "/api/v1/bots",
        json={"name": "phase1-multi-bot"},
        headers=_auth_only(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text
    bot = resp.json()
    ctx["bot"] = bot

    for worker_name in (w1, w2):
        wresp = client.post(
            f"/api/v1/bots/{bot['id']}/workers",
            json={
                "name": worker_name,
                "description": f"{worker_name} worker",
            },
            headers=_auth_only(ctx["headers"]),
        )
        assert wresp.status_code in (200, 201), wresp.text


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        '我送出 POST /api/v1/agent/chat/stream 帶 identity_source "{src}"'
    )
)
def post_stream_with_source(ctx, client, src):
    _post_stream(client, ctx, {
        "message": "hi",
        "bot_id": ctx["bot"]["id"],
        "identity_source": src,
    })


@when(
    parsers.parse(
        '我送出 POST /api/v1/agent/chat/stream 帶 identity_source '
        '"{src}" 訊息 "{msg}"'
    )
)
def post_stream_with_source_and_msg(ctx, client, src, msg):
    _post_stream(client, ctx, {
        "message": msg,
        "bot_id": ctx["bot"]["id"],
        "identity_source": src,
    })


@when("我送出 POST /api/v1/agent/chat/stream 不帶 identity_source")
def post_stream_no_source(ctx, client):
    _post_stream(client, ctx, {
        "message": "hi",
        "bot_id": ctx["bot"]["id"],
    })


@when("agent 執行過程中發生錯誤後送出 POST /api/v1/agent/chat/stream")
def post_stream_with_failure(ctx, client, app):
    # 切換 agent_service 到 _FailingFakeAgent — 用直接 override 取代 factory 開關
    app.container.agent_service.override(
        providers.Singleton(_FailingFakeAgent)
    )
    _post_stream(client, ctx, {
        "message": "hi",
        "bot_id": ctx["bot"]["id"],
        "identity_source": "studio",
    })


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("SSE done 事件應包含 trace_id 欄位")
def check_done_has_trace_id(ctx):
    assert ctx.get("trace_id"), (
        f"done event missing trace_id; events: {ctx['sse_events']}"
    )


@then("SSE 事件中至少一筆帶 node_id 應對應到 DB trace 的 nodes[]")
def check_events_have_node_id(ctx, test_engine):
    events_with_node_id = [
        e for e in ctx["sse_events"]
        if e.get("node_id") and isinstance(e.get("node_id"), str)
    ]
    assert events_with_node_id, (
        f"no event carries node_id; events: {ctx['sse_events']}"
    )

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    async def _query():
        sf = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with sf() as session:
            row = await session.execute(
                text("SELECT nodes FROM agent_execution_traces "
                     "WHERE trace_id = :tid"),
                {"tid": ctx["trace_id"]},
            )
            return row.scalar_one_or_none()

    nodes = asyncio.get_event_loop().run_until_complete(_query()) or []
    trace_node_ids = {n.get("node_id") for n in nodes}

    cross_match = [
        e for e in events_with_node_id
        if e["node_id"] in trace_node_ids
    ]
    assert cross_match, (
        f"event node_ids {[e['node_id'] for e in events_with_node_id]} "
        f"do not appear in trace.nodes {trace_node_ids}"
    )


@then(
    parsers.parse('SSE 事件序列應包含一筆 type 為 "{etype}" 的事件')
)
def check_event_type_present(ctx, etype):
    matched = [e for e in ctx["sse_events"] if e.get("type") == etype]
    assert matched, (
        f"no '{etype}' event found; types: "
        f"{[e.get('type') for e in ctx['sse_events']]}"
    )
    ctx["matched_event"] = matched[0]


@then(parsers.parse("該事件應含 {field} 欄位"))
def check_matched_event_has_field(ctx, field):
    assert field in ctx["matched_event"], (
        f"matched event missing {field}: {ctx['matched_event']}"
    )


@then(parsers.parse('DB 中該 trace 應有至少一筆 outcome 為 "{outcome}" 的節點'))
def check_trace_has_failed_node(ctx, test_engine, outcome):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    async def _query():
        sf = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with sf() as session:
            row = await session.execute(
                text("SELECT nodes FROM agent_execution_traces "
                     "WHERE trace_id = :tid"),
                {"tid": ctx["trace_id"]},
            )
            return row.scalar_one_or_none()

    nodes = asyncio.get_event_loop().run_until_complete(_query()) or []
    matched = [n for n in nodes if n.get("outcome") == outcome]
    assert matched, (
        f"no node with outcome={outcome}; nodes outcomes: "
        f"{[n.get('outcome') for n in nodes]}"
    )
    ctx["failed_node"] = matched[0]


@then(parsers.parse("該節點 metadata 應含 {field} 欄位"))
def check_failed_node_metadata(ctx, field):
    metadata = ctx["failed_node"].get("metadata", {})
    assert field in metadata, (
        f"failed node metadata missing {field}: {metadata}"
    )


@then(parsers.parse('DB 中該 trace_id 對應的 trace.source 應為 "{expected}"'))
def check_trace_source(ctx, test_engine, expected):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    async def _query():
        sf = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with sf() as session:
            row = await session.execute(
                text("SELECT source FROM agent_execution_traces "
                     "WHERE trace_id = :tid"),
                {"tid": ctx["trace_id"]},
            )
            return row.scalar_one_or_none()

    source = asyncio.get_event_loop().run_until_complete(_query())
    assert source == expected, f"Expected source={expected}, got {source}"


@then(parsers.parse('DB 中該 trace 所有節點的 outcome 應為 "{expected}"'))
def check_all_nodes_success(ctx, test_engine, expected):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    async def _query():
        sf = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with sf() as session:
            row = await session.execute(
                text("SELECT nodes FROM agent_execution_traces "
                     "WHERE trace_id = :tid"),
                {"tid": ctx["trace_id"]},
            )
            return row.scalar_one_or_none()

    nodes = asyncio.get_event_loop().run_until_complete(_query()) or []
    outcomes = [n.get("outcome", "success") for n in nodes]
    assert all(o == expected for o in outcomes), (
        f"some nodes outcome != {expected}: {outcomes}"
    )
