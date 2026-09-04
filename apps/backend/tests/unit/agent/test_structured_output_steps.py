"""結構化輸出（output_format / 供應商能力等級）BDD Step Definitions（Issue #70）"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.direct_retrieval_service import DirectRetrievalService
from src.application.agent.intent_classifier import ClassifyOutcome
from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import RetrieveResult
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId
from src.domain.llm.structured_output import capability, is_strict_compatible
from src.domain.rag.value_objects import Source
from src.domain.shared.exceptions import ValidationError

scenarios("unit/agent/structured_output.feature")

_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "category": {"type": "string"},
        "answer": {"type": "string"},
    },
    "required": ["status"],
}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _sources(score):
    return [Source(
        document_name="FAQ", content_snippet="板橋店 2 樓設有快剪",
        score=score, chunk_id="c-1",
    )]


def _text(value: str) -> str:
    """feature 以 "-" 代表空字串；字面 \\n 還原為換行。"""
    if value == "-":
        return ""
    return value.replace("\\n", "\n")


def _spy_trace(context, uc):
    original = uc._persist_agent_trace

    async def spy(**kwargs):
        trace_id, nodes = await original(**kwargs)
        context["trace_nodes"] = nodes or []
        return trace_id, nodes

    uc._persist_agent_trace = spy


def _setup_web(
    context, *, mode="kb", score=0.85, output_format="text", provider="",
    model="", miss_reply="", schema=None, text_field="answer", replies=None,
):
    bot = Bot(
        id=BotId(value="bot-so"), tenant_id="t1", name="SO", base_prompt="p",
        knowledge_base_ids=["kb-1"], mode=mode, output_format=output_format,
        output_schema=schema, miss_reply=miss_reply, llm_provider=provider,
        llm_model=model, output_text_field=text_field,
    )
    agent = AsyncMock()
    default_reply = (
        '{"status":"km","category":"marketing","answer":"可以"}'
        if output_format == "json" else "答"
    )
    replies = list(replies or [default_reply])

    async def _reply(**_kwargs):
        # 依序回覆，超過清單長度則重複最後一則（重試路徑不會耗盡）
        idx = min(len(context.setdefault("_calls", [])), len(replies) - 1)
        context["_calls"].append(_kwargs)
        return AgentResponse(answer=replies[idx])

    agent.process_message = AsyncMock(side_effect=_reply)
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=[])
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(return_value=ClassifyOutcome(
        worker=None, query="", is_attack=False,
    ))
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(score),
    ))
    context.update(agent=agent, query_rag=query_rag)
    uc = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        intent_classifier=classifier,
        worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )
    _spy_trace(context, uc)
    context["uc"] = uc
    context["conv_repo"] = conv_repo


# ── 能力表 ──


@given(parsers.parse('供應商 "{provider}" 模型 "{model}"'))
def given_provider_model(context, provider, model):
    context["provider"], context["model"] = provider, model


@when("查詢結構化輸出能力")
def query_capability(context):
    context["tier"], context["note"] = capability(context["provider"], context["model"])


@then(parsers.parse('能力等級應為 "{tier}"'))
def tier_is(context, tier):
    assert context["tier"] == tier, (context["tier"], context["note"])


# ── 能力查詢端點 ──


@given("已登入的租戶管理員")
def logged_in_admin(context):
    from src.interfaces.api.deps import CurrentTenant, get_current_tenant
    from src.interfaces.api.llm_capability_router import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_tenant] = lambda: CurrentTenant(
        tenant_id="t1", role="tenant_admin",
    )
    context["client"] = TestClient(app)


@when(parsers.parse('以 GET 查詢 "{path}"'))
def http_get(context, path):
    context["http"] = context["client"].get(path)


@then(parsers.parse("回應狀態應為 {code:d}"))
def status_is(context, code):
    assert context["http"].status_code == code, context["http"].text


@then(parsers.parse('回應 tier 應為 "{tier}"'))
def response_tier_is(context, tier):
    assert context["http"].json()["tier"] == tier


# ── bot 欄位驗證 ──


@given("一個既有的 bot")
def existing_bot(context):
    bot = Bot(id=BotId(value="bot-m"), tenant_id="t1", name="M")
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=bot)
    repo.save = AsyncMock()
    context["bot"] = bot
    context["bot_uc"] = UpdateBotUseCase(bot_repository=repo)


def _update(context, **fields):
    try:
        _run(context["bot_uc"].execute(UpdateBotCommand(bot_id="bot-m", **fields)))
        context["outcome"] = "saved"
    except (ValidationError, ValueError):
        context["outcome"] = "error"


@when(parsers.re(r'將 bot output_format 更新為 "(?P<fmt>\w+)"$'))
def update_format(context, fmt):
    _update(context, output_format=fmt)


@when(parsers.re(
    r'將 bot output_format 更新為 "(?P<fmt>\w+)" 且 schema 為 "(?P<schema>[^"]+)"$'
))
def update_format_with_schema(context, fmt, schema):
    _update(context, output_format=fmt, output_schema=schema)


@when(parsers.re(
    r"將 bot output_format 更新為 \"(?P<fmt>\w+)\" 且未命中話術為 '(?P<miss>.+)'$"
))
def update_format_with_miss(context, fmt, miss):
    _update(context, output_format=fmt, miss_reply=miss)


@when(parsers.re(
    r"將 bot output_format 更新為 \"(?P<fmt>\w+)\"、schema 要求 \"(?P<field>\w+)\" 欄位"
    r"且未命中話術為 '(?P<miss>.+)'$"
))
def update_format_schema_miss(context, fmt, field, miss):
    schema = {
        "type": "object",
        "properties": {field: {"type": "string"}},
        "required": [field],
    }
    _update(context, output_format=fmt, output_schema=schema, miss_reply=miss)


@then(parsers.parse("結果應為 {outcome}"))
def outcome_is(context, outcome):
    assert context["outcome"] == outcome


# ── web 管線 ──


@given(parsers.re(
    r'一個 mode 為 "(?P<mode>\w+)"、output_format 為 "(?P<fmt>\w+)" 且供應商為 '
    r'"(?P<provider>\w+)" 的 bot，檢索分數 (?P<score>[\d.]+)$'
))
def bot_with_provider(context, mode, fmt, provider, score):
    model = {
        "google": "gemini-3.7-flash", "deepseek": "deepseek-chat",
        "openai": "gpt-4o", "anthropic": "claude-sonnet-4-5",
    }.get(provider, "")
    _setup_web(
        context, mode=mode, score=float(score), output_format=fmt,
        provider=provider, model=model, schema=_SCHEMA,
    )


@given(parsers.re(
    r'一個 mode 為 "(?P<mode>\w+)"、output_format 為 "(?P<fmt>\w+)" 且未命中話術為 '
    r'"(?P<miss>[^"]+)" 的 bot，檢索分數 (?P<score>[\d.]+)$'
))
def bot_with_miss(context, mode, fmt, miss, score):
    _setup_web(
        context, mode=mode, score=float(score), output_format=fmt,
        miss_reply=_text(miss), provider="google", model="gemini-3.7-flash",
    )


@given(parsers.re(
    r'一個 mode 為 "(?P<mode>\w+)"、output_format 為 "(?P<fmt>\w+)" 的 bot，'
    r"模型回覆 '(?P<reply>.+)'$"
))
def bot_with_reply(context, mode, fmt, reply):
    _setup_web(
        context, mode=mode, output_format=fmt,
        schema=_SCHEMA if fmt == "json" else None, replies=[_text(reply)],
    )


@given(parsers.re(
    r'一個 mode 為 "(?P<mode>\w+)"、output_format 為 "(?P<fmt>\w+)"、輸出文字欄位為 '
    r'"(?P<field>\w+)" 的 bot，模型回覆 \'(?P<reply>.+)\'$'
))
def bot_with_text_field(context, mode, fmt, field, reply):
    _setup_web(
        context, mode=mode, output_format=fmt, text_field=field,
        replies=[_text(reply)],
    )


@given(parsers.re(
    r'一個 mode 為 "(?P<mode>\w+)"、output_format 為 "(?P<fmt>\w+)" 的 bot，'
    r"模型第一次回覆 '(?P<r1>.+?)'、第二次回覆 '(?P<r2>.+)'$"
))
def bot_with_two_replies(context, mode, fmt, r1, r2):
    _setup_web(
        context, mode=mode, output_format=fmt, schema=_SCHEMA,
        replies=[_text(r1), _text(r2)],
    )


@given(parsers.re(
    r'一個 mode 為 "(?P<mode>\w+)"、output_format 為 "(?P<fmt>\w+)" 且未命中話術為 '
    r"'(?P<miss>.+?)' 的 bot，模型兩次都回覆 '(?P<reply>.+)'$"
))
def bot_with_two_bad_replies(context, mode, fmt, miss, reply):
    _setup_web(
        context, mode=mode, output_format=fmt, schema=_SCHEMA,
        miss_reply=_text(miss), replies=[_text(reply), _text(reply)],
    )


@when("以 web 送出訊息")
def send_web(context):
    cmd = SendMessageCommand(tenant_id="t1", bot_id="bot-so", message="板橋店有快剪嗎")
    context["response"] = _run(context["uc"].execute(cmd))
    conversation = context["conv_repo"].save.call_args.args[0]
    context["assistant_msg"] = conversation.messages[-1]


@then("Agent 應收到 llm_params 含 response_schema")
def agent_got_schema(context):
    kwargs = context["agent"].process_message.call_args.kwargs
    assert "response_schema" in kwargs["llm_params"], kwargs["llm_params"]
    assert "response_json_object" not in kwargs["llm_params"]


@then("Agent 應收到 llm_params 含 response_json_object")
def agent_got_json_object(context):
    kwargs = context["agent"].process_message.call_args.kwargs
    params = kwargs["llm_params"]
    assert params.get("response_json_object") is True, params
    assert "response_schema" not in kwargs["llm_params"]


@then("Agent 收到的系統提示應含 schema 描述")
def prompt_has_schema(context):
    kwargs = context["agent"].process_message.call_args.kwargs
    assert "【輸出格式】" in kwargs["system_prompt"]
    assert '"status"' in kwargs["system_prompt"]


@then(parsers.parse('回覆 structured_content.output 的 "{key}" 應為 "{value}"'))
def output_key_is(context, key, value):
    sc = context["assistant_msg"].structured_content
    assert sc and sc.get("output"), sc
    assert sc["output"][key] == value


@then("回覆內容應為合法 JSON")
def reply_is_json(context):
    parsed = json.loads(context["response"].answer)
    assert isinstance(parsed, dict)


@then(parsers.parse("Agent 應被呼叫 {n:d} 次"))
def agent_called_n(context, n):
    assert context["agent"].process_message.await_count == n


@then("Agent 不應被呼叫")
def agent_not_called(context):
    context["agent"].process_message.assert_not_awaited()


@then(parsers.parse('回覆內容應為 "{text}"'))
def reply_is(context, text):
    assert context["response"].answer == _text(text), repr(context["response"].answer)


@then(parsers.parse('trace 應含 status 為 "{status}" 的 "{node_type}" 節點'))
def trace_has_status_node(context, status, node_type):
    nodes = context.get("trace_nodes", [])
    matched = [
        n for n in nodes
        if n.get("node_type") == node_type
        and (n.get("metadata") or {}).get("status") == status
    ]
    assert matched, [(n.get("node_type"), n.get("metadata")) for n in nodes]


@then(parsers.parse('回覆 structured_content.display_text 應為 "{text}"'))
def display_text_is(context, text):
    sc = context["assistant_msg"].structured_content
    assert sc and sc.get("display_text") == text, sc


@then(parsers.parse(
    "回覆 structured_content.retrieval 的 top_score 應為 {score:g} 且 miss 應為 {miss}"
))
def retrieval_stats_are(context, score, miss):
    sc = context["assistant_msg"].structured_content
    assert sc and sc.get("retrieval"), sc
    stats = sc["retrieval"]
    assert stats["top_score"] == pytest.approx(score)
    assert stats["miss"] is (miss == "true")
    assert "threshold" in stats and "chunk_count" in stats


# ── LINE ──


@given(parsers.re(
    r'LINE 用例與 mode 為 "(?P<mode>\w+)"、output_format 為 "(?P<fmt>\w+)"'
    r'(?:、輸出文字欄位為 "(?P<field>\w+)"|、輸出文字欄位為預設值)?\s*的 bot，'
    r"模型回覆 '(?P<reply>.+)'$"
))
def line_setup(context, mode, fmt, field, reply):
    bot = Bot(
        tenant_id="t1", name="SO", line_channel_secret="s",
        line_channel_access_token="t", knowledge_base_ids=["kb-1"], mode=mode,
        output_format=fmt, output_text_field=field or "answer",
    )
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer=_text(reply)))
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(0.9),
    ))
    context.update(agent=agent, line_service=line_service)
    context["line_uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=bot_repo, line_service_factory=factory,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )


@when("系統處理一則 LINE 訊息")
def line_process(context):
    body = json.dumps({"events": [{
        "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
        "message": {"type": "text", "text": "配送幾班"},
        "timestamp": 1700000000000, "webhookEventId": "evt-so-1",
    }]})
    _run(context["line_uc"].execute_for_bot("shop", body, "sig"))


@then(parsers.parse('LINE 回覆文字應為 "{text}"'))
def line_reply_is(context, text):
    call = context["line_service"].reply_with_quick_reply.call_args
    assert call.args[1] == text, call.args[1]


# ── strict 相容性 ──

_CLOSED_ITEM = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
    "additionalProperties": False,
}
_OPEN_ITEM = {"type": "object", "properties": {"name": {"type": "string"}}}
_STRICT_SCHEMAS = {
    "closed": _CLOSED_ITEM,
    "open": _OPEN_ITEM,
    "nested-open": {
        "type": "object",
        "properties": {"items": {"type": "array", "items": _OPEN_ITEM}},
        "required": ["items"],
        "additionalProperties": False,
    },
    "nested-closed": {
        "type": "object",
        "properties": {"items": {"type": "array", "items": _CLOSED_ITEM}},
        "required": ["items"],
        "additionalProperties": False,
    },
}


@given(parsers.parse('一個 "{kind}" 的 JSON schema'))
def given_schema(context, kind):
    context["schema"] = _STRICT_SCHEMAS[kind]


@when("判定 strict 相容性")
def judge_strict(context):
    context["strict"] = is_strict_compatible(context["schema"])


@then(parsers.parse("strict 應為 {value}"))
def strict_is(context, value):
    assert context["strict"] is (value == "true")
