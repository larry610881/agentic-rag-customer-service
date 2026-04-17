"""Bot Studio Integration — BDD Step Definitions.

Validates that:
1. ChatRequest accepts `identity_source` and persists into agent_execution_traces.source
2. Stream `done` event includes `trace_id` so frontend can fetch full trace
3. Backwards-compat: omitting identity_source defaults to "web"
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from dependency_injector import providers
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.agent.services import AgentService
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

scenarios("integration/agent/bot_studio.feature")


class _StudioFakeAgent(AgentService):
    """Minimal fake — 模擬真實 agent 行為：start trace、yield 一個 token、加 final node。
    不依賴任何 LLM provider，讓 use_case stream 完整跑到 _persist_agent_trace。
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
        yield {"type": "token", "content": "ok"}
        AgentTraceCollector.add_node(
            "final_response", "最終回覆", None, 1.0, 1.0,
        )


@pytest.fixture
def ctx():
    return {}


@pytest.fixture(autouse=True)
def _override_agent_service(app, test_engine):
    """避開 _resolve_llm_model 對 OpenAI key 的硬性依賴 — 用 minimal fake
    跑完整 stream 流程，讓 trace 順利持久化並回傳 trace_id。

    同時 override trace_session_factory 讓 _persist_agent_trace 寫到 test DB
    而非 dev DB（既有測試對 trace 持久化沒驗證，所以 default 沒注意到）。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    app.container.agent_service.override(providers.Singleton(_StudioFakeAgent))
    app.container.trace_session_factory.override(
        providers.Object(test_session_factory)
    )
    yield
    app.container.agent_service.reset_override()
    app.container.trace_session_factory.reset_override()


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


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
        json={"name": "studio-test-bot"},
        headers=_auth_only(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text
    ctx["bot"] = resp.json()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


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
    ctx["stream_response"] = resp
    ctx["sse_events"] = events


@when(
    parsers.parse(
        '我送出 POST /api/v1/agent/chat/stream 帶 identity_source "{src}"'
    )
)
def post_chat_stream_with_source(ctx, client, src):
    _post_stream(client, ctx, {
        "message": "hi",
        "bot_id": ctx["bot"]["id"],
        "identity_source": src,
    })


@when("我送出 POST /api/v1/agent/chat/stream 不帶 identity_source")
def post_chat_stream_no_source(ctx, client):
    _post_stream(client, ctx, {
        "message": "hi",
        "bot_id": ctx["bot"]["id"],
    })


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("SSE done 事件應包含 trace_id 欄位")
def check_done_has_trace_id(ctx):
    done_events = [e for e in ctx["sse_events"] if e.get("type") == "done"]
    assert done_events, f"no done event found in: {ctx['sse_events']}"
    done = done_events[0]
    assert "trace_id" in done and done["trace_id"], (
        f"done event missing trace_id: {done}"
    )
    ctx["trace_id"] = done["trace_id"]


@then(parsers.parse('DB 中該 trace_id 對應的 trace.source 應為 "{expected}"'))
def check_trace_source_in_db(ctx, test_engine, expected):
    """直接查 test DB 驗證 trace 持久化 — 避開 observability_router 直接 import
    模組層 async_session_factory（綁定 dev DB）的既有技術債（read-path DI 修復
    屬於另一 sprint 範圍）。
    """
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    trace_id = ctx["trace_id"]

    async def _query():
        sf = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with sf() as session:
            row = await session.execute(
                text(
                    "SELECT source FROM agent_execution_traces "
                    "WHERE trace_id = :tid"
                ),
                {"tid": trace_id},
            )
            return row.scalar_one_or_none()

    source = asyncio.get_event_loop().run_until_complete(_query())
    assert source == expected, f"Expected source={expected}, got {source}"
