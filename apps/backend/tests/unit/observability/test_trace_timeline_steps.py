"""Trace 時間軸儀表點 BDD Step Definitions（Issue #57）"""

import asyncio
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import (
    QueryRAGCommand,
    QueryRAGUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId
from src.domain.conversation.entity import Conversation
from src.domain.rag.value_objects import SearchResult
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeEmbeddingService,
    FakeKbRepo,
    FakeVectorStore,
    make_kb,
    run,
)

scenarios("unit/observability/trace_timeline.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context(monkeypatch):
    """攔截 AgentTraceCollector.finish 拿到最終 trace（含 request 根節點）。"""
    captured: list = []
    original = AgentTraceCollector.finish

    def _spy(total_ms):
        trace = original(total_ms)
        if trace is not None:
            captured.append(trace)
        return trace

    monkeypatch.setattr(AgentTraceCollector, "finish", staticmethod(_spy))
    yield {"captured": captured}
    AgentTraceCollector.finish(0.0)


def _types(trace) -> list[str]:
    return [n.node_type for n in trace.nodes]


def _root(trace):
    roots = [n for n in trace.nodes if n.node_type == "request"]
    assert len(roots) == 1, _types(trace)
    return roots[0]


# ── collector ──


@given(parsers.parse("一個以 {ms:d} 毫秒前為 t0 啟動的 trace"))
def start_with_t0(context, ms):
    context["trace"] = AgentTraceCollector.start(
        tenant_id="t1", agent_mode="react", t0=time.monotonic() - ms / 1000,
    )


@given(parsers.parse('trace 內有一個無父節點的 "{node_type}" 節點'))
def add_orphan_node(context, node_type):
    context["orphan_id"] = AgentTraceCollector.add_node(
        node_type=node_type, label="llm", parent_id=None,
        start_ms=10.0, end_ms=20.0,
    )


@when("呼叫 wrap_request")
def call_wrap(context):
    context["root_id"] = AgentTraceCollector.wrap_request()


@then(parsers.parse('trace 應有一個 node_type 為 "{node_type}" 且無父節點的根節點'))
def has_root(context, node_type):
    root = _root(context["trace"])
    assert root.parent_id is None and root.node_id == context["root_id"]


@then(parsers.parse('原本無父節點的 "{node_type}" 節點 parent_id 應指向根節點'))
def orphan_reparented(context, node_type):
    node = next(n for n in context["trace"].nodes if n.node_id == context["orphan_id"])
    assert node.parent_id == context["root_id"]


@then(parsers.parse("根節點 start_ms 應為 0 且 end_ms 至少 {ms:d}"))
def root_span(context, ms):
    root = _root(context["trace"])
    assert root.start_ms == 0.0 and root.end_ms >= ms


# ── web / widget ──


@given("一個有 2 則歷史訊息的既有對話與正常設定的 bot")
def web_setup(context):
    bot = Bot(id=BotId(value="bot-1"), tenant_id="t1", name="b", base_prompt="p")
    conv = Conversation(tenant_id="t1", bot_id="bot-1")
    conv.add_message("user", "先前問題")
    conv.add_message("assistant", "先前回答")
    agent = AsyncMock()
    agent.process_message.return_value = AgentResponse(answer="回答")

    async def _stream(**_kwargs):
        yield {"type": "token", "content": "回答"}
        yield {"type": "done"}

    agent.process_message_stream = _stream
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = conv
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    context["uc"] = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
    )
    context["conv_id"] = conv.id.value


@when(parsers.parse('以來源 "{source}" 以非串流方式送出訊息並攔截 finish 的 trace'))
def web_send(context, source):
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-1", message="測試",
        conversation_id=context["conv_id"], identity_source=source,
    )
    _run(context["uc"].execute(cmd))
    context["trace"] = context["captured"][-1]


@when("以串流方式送出訊息並攔截 finish 的 trace")
def web_send_stream(context):
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-1", message="測試",
        conversation_id=context["conv_id"],
    )

    async def _consume():
        async for _ in context["uc"].execute_stream(cmd):
            pass

    _run(_consume())
    context["trace"] = context["captured"][-1]


@then(parsers.parse("trace 節點應依序包含 {types}"))
def nodes_in_order(context, types):
    expected = json.loads(f"[{types}]")
    actual = _types(context["trace"])
    positions = []
    for t in expected:
        assert t in actual, f"{t} missing in {actual}"
        positions.append(actual.index(t))
    assert positions == sorted(positions), f"order {expected} vs {actual}"


@then(parsers.parse('trace 應有 "{node_type}" 根節點且 total_ms 等於根節點 end_ms'))
def root_matches_total(context, node_type):
    root = _root(context["trace"])
    assert root.node_type == node_type
    assert context["trace"].total_ms == root.end_ms


@then("所有非根節點的 parent_id 都不為 None")
def all_parented(context):
    root = _root(context["trace"])
    for n in context["trace"].nodes:
        if n.node_id != root.node_id:
            assert n.parent_id is not None, n.node_type


# ── LINE ──


@given(parsers.parse('Bot "{short_code}" 設定了 LINE Channel 且 Agent 回覆 "{answer}"'))
def line_setup(context, short_code, answer):
    bot = Bot(
        tenant_id="tenant-abc", name="Shop A",
        line_channel_secret="secret-001", line_channel_access_token="token-001",
        knowledge_base_ids=["kb-default"],
    )
    repo = AsyncMock()
    repo.find_by_short_code = AsyncMock(return_value=bot)
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer=answer))
    context["short_code"] = short_code
    context["uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=repo, line_service_factory=factory,
    )


@when("以 execute_for_bot 處理 LINE 文字事件並攔截 finish 的 trace")
def line_execute(context):
    body = json.dumps({"events": [{
        "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
        "message": {"type": "text", "text": "退貨"}, "timestamp": 1700000000000,
        "webhookEventId": "evt-tl-1",
    }]})
    _run(context["uc"].execute_for_bot(context["short_code"], body, "sig"))
    context["trace"] = context["captured"][-1]


# ── RAG ──


@given(parsers.parse(
    '租戶 "{tenant_id}" 的 KB "{kb_id}" 有 {n:d} 筆已 embed 的 chunks 且已啟動 trace'
))
def rag_setup(context, tenant_id, kb_id, n):
    kb_repo = FakeKbRepo()
    vs = FakeVectorStore()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    vs.search_results = [
        SearchResult(
            id=f"c-{i}", score=0.9 - i * 0.1,
            payload={"content": f"片段 {i}", "tenant_id": tenant_id,
                     "document_id": "d1", "document_name": "doc"},
        )
        for i in range(n)
    ]
    context["rag_uc"] = QueryRAGUseCase(
        knowledge_base_repository=kb_repo,
        embedding_service=FakeEmbeddingService(),
        vector_store=vs,
        llm_service=None,
    )
    context["cmd"] = QueryRAGCommand(tenant_id=tenant_id, kb_id=kb_id, query="q")
    context["trace"] = AgentTraceCollector.start(
        tenant_id=tenant_id, agent_mode="react"
    )


@when("執行 retrieve")
def rag_retrieve(context):
    run(context["rag_uc"].retrieve(context["cmd"]))


@then(parsers.parse('應有 "{a}" 與 "{b}" 節點且 parent 為 "{parent_type}" 節點'))
def rag_children(context, a, b, parent_type):
    nodes = context["trace"].nodes
    by_id = {n.node_id: n for n in nodes}
    for t in (a, b):
        node = next((n for n in nodes if n.node_type == t), None)
        assert node is not None, _types(context["trace"])
        assert node.parent_id in by_id
        assert by_id[node.parent_id].node_type == parent_type


@then(parsers.parse('"{a}" 應在 "{b}" 之前結束'))
def rag_order(context, a, b):
    nodes = context["trace"].nodes
    na = next(n for n in nodes if n.node_type == a)
    nb = next(n for n in nodes if n.node_type == b)
    assert na.end_ms <= nb.end_ms


_ = datetime, timezone
