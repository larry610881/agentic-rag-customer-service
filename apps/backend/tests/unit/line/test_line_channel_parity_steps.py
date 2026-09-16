"""Issue #99 二-2/3/6：LINE 通路對等（trace / 攔截回應 / 記憶）。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.guard_responses import blocked_input_response
from src.application.agent.output_format import OutputSpec
from src.application.agent.trace_persistence import persist_finished_trace
from src.application.line.handle_webhook_use_case import (
    HandleWebhookUseCase,
    WebhookContext,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.line.entity import LineTextMessageEvent

scenarios("unit/line/line_channel_parity.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


# ── trace 持久化 ──────────────────────────────────────────────


class _FakeSession:
    def __init__(self, sink):
        self._sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add(self, row):
        self._sink.append(row)

    async def commit(self):
        pass


@given("一個含 failed 節點的已完成 trace 與假的 session factory")
def finished_trace(ctx):
    node_ok = SimpleNamespace(to_dict=lambda: {"node_type": "a", "outcome": "success"})
    node_bad = SimpleNamespace(to_dict=lambda: {"node_type": "b", "outcome": "failed"})
    ctx["trace"] = SimpleNamespace(
        trace_id="tr-1", tenant_id="t1", agent_mode="react", source="web",
        llm_model="m", llm_provider="p", bot_id="b1", nodes=[node_ok, node_bad],
        total_ms=12.0, total_tokens=None, config_hash="h", abuse_level=None,
        conversation_id=None, message_id=None,
    )
    ctx["rows"] = []
    ctx["factory"] = lambda: _FakeSession(ctx["rows"])


@when(parsers.parse('以 source "{source}" 呼叫 persist_finished_trace'))
def call_persist(ctx, source):
    ctx["trace_id"] = _run(
        persist_finished_trace(
            ctx["trace"], ctx["factory"], conversation_id="c1", message_id="m1",
            source=source,
        )
    )


@then(parsers.parse(
    '寫入一列 agent_execution_traces，source 為 "{source}" 且 outcome 為 "{outcome}"'
))
def assert_row(ctx, source, outcome):
    assert ctx["trace_id"] == "tr-1"
    assert len(ctx["rows"]) == 1
    row = ctx["rows"][0]
    assert row.source == source and row.outcome == outcome
    assert row.conversation_id == "c1" and row.message_id == "m1"


# ── 攔截回應 ──────────────────────────────────────────────────


@given("一個 output_format 為 json 的 OutputSpec 與被攔截的 guard 結果")
def json_spec(ctx):
    ctx["spec"] = OutputSpec.from_cfg({
        "output_format": "json",
        "output_schema": None,
        "output_text_field": "answer",
    })
    ctx["guard_result"] = SimpleNamespace(
        passed=False, blocked_response="很抱歉，無法回答", rule_matched="rule-1"
    )


@when("以 blocked_input_response 組回應")
def build_blocked(ctx):
    ctx["resp"] = blocked_input_response(ctx["guard_result"], ctx["spec"])


@then('回應的 guard_blocked 為 "input"、answer 為 JSON 字串且 structured_output 為物件')
def assert_blocked(ctx):
    resp = ctx["resp"]
    assert isinstance(resp, AgentResponse)
    assert resp.guard_blocked == "input" and resp.guard_rule_matched == "rule-1"
    assert isinstance(json.loads(resp.answer), dict)
    assert isinstance(resp.structured_output, dict)


# ── LINE 記憶 ─────────────────────────────────────────────────


def _bot(memory_enabled=True, threshold=3):
    return Bot(
        id=BotId(value="bot-line"),
        short_code=BotShortCode(value="sc"),
        tenant_id="tenant-line",
        name="Line Bot",
        knowledge_base_ids=["kb"],
        memory_enabled=memory_enabled,
        memory_extraction_threshold=threshold,
    )


def _setup(ctx, bot, memory_service):
    agent = AsyncMock()

    async def process_message(**kwargs):
        ctx["agent_kwargs"] = kwargs
        return AgentResponse(answer="推薦無糖茶")

    agent.process_message = AsyncMock(side_effect=process_message)
    ctx["agent"] = agent
    ctx["line_service"] = AsyncMock()
    conv_repo = AsyncMock()
    conv_repo.find_latest_by_visitor = AsyncMock(return_value=None)
    ctx["uc"] = HandleWebhookUseCase(
        agent_service=agent,
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        conversation_repository=conv_repo,
        memory_service=memory_service,
    )
    ctx["bot"] = bot


@given(parsers.parse('一個開啟記憶的 LINE bot 與會回傳記憶 "{memory}" 的記憶服務'))
def bot_with_memory(ctx, memory):
    svc = SimpleNamespace(
        load_prompt=AsyncMock(return_value=memory),
        schedule_extraction=AsyncMock(return_value=False),
    )
    ctx["memory_service"] = svc
    _setup(ctx, _bot(), svc)


@given("一個開啟記憶且門檻為 1 的 LINE bot 與記憶服務")
def bot_threshold_one(ctx):
    svc = SimpleNamespace(
        load_prompt=AsyncMock(return_value=""),
        schedule_extraction=AsyncMock(return_value=True),
    )
    ctx["memory_service"] = svc
    _setup(ctx, _bot(threshold=1), svc)


@given("一個開啟記憶的 LINE bot 但沒有記憶服務")
def bot_no_service(ctx):
    _setup(ctx, _bot(), None)


@when(parsers.parse('LINE 用戶 "{user_id}" 送出 "{text}"'))
def send_line(ctx, user_id, text):
    context = WebhookContext(
        bot=ctx["bot"],
        short_code="sc",
        line_service=ctx["line_service"],
        events=[LineTextMessageEvent(
            reply_token="tk", user_id=user_id, message_text=text, timestamp=1,
        )],
    )
    try:
        _run(ctx["uc"].process_and_push(context))
        ctx["error"] = None
    except Exception as e:  # noqa: BLE001
        ctx["error"] = e


@then(parsers.parse('傳給 agent 的 history_context 以 "{prefix}" 開頭'))
def history_prefixed(ctx, prefix):
    assert ctx.get("error") is None, ctx.get("error")
    assert ctx["agent_kwargs"]["history_context"].startswith(prefix)


@then(parsers.parse('記憶服務以 source "{source}" 與 external_id "{ext}" 載入'))
def loaded_with(ctx, source, ext):
    kwargs = ctx["memory_service"].load_prompt.await_args.kwargs
    assert kwargs["source"] == source and kwargs["external_id"] == ext
    assert kwargs["memory_enabled"] is True


@then(parsers.parse('記憶服務收到一次萃取排程，source 為 "{source}"'))
def extraction_scheduled(ctx, source):
    assert ctx.get("error") is None, ctx.get("error")
    svc = ctx["memory_service"]
    assert svc.schedule_extraction.await_count == 1
    kwargs = svc.schedule_extraction.await_args.kwargs
    assert kwargs["source"] == source and kwargs["threshold"] == 1


@then("agent 正常被呼叫且沒有例外")
def agent_called(ctx):
    assert ctx.get("error") is None, ctx.get("error")
    ctx["agent"].process_message.assert_awaited_once()
