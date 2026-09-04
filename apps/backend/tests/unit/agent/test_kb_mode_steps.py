"""知識庫問答模式（bot mode kb）BDD Step Definitions（Issue #70）"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
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
from src.domain.bot.entity import DEFAULT_MISS_REPLY, Bot
from src.domain.bot.value_objects import BotId
from src.domain.prompt_gate.config_snapshot import diff_snapshots, take_snapshot
from src.domain.rag.value_objects import Source
from src.domain.shared.exceptions import ValidationError

scenarios("unit/agent/kb_mode.feature")


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
    """feature 以 "-" 代表空字串（parsers.parse 無法比對空字串）。"""
    return "" if value == "-" else value


def _spy_trace(context, uc):
    """攔截 _persist_agent_trace 以取得 trace 節點（不落庫、不需 test_mode）。"""
    original = uc._persist_agent_trace

    async def spy(**kwargs):
        trace_id, nodes = await original(**kwargs)
        context["trace_nodes"] = nodes or []
        return trace_id, nodes

    uc._persist_agent_trace = spy


def _setup_web(context, *, mode, score, rerank=False, memory=False, miss_reply=""):
    bot = Bot(
        id=BotId(value="bot-kb"), tenant_id="t1", name="KB", base_prompt="p",
        knowledge_base_ids=["kb-1"], rerank_enabled=rerank, mode=mode,
        memory_enabled=memory, memory_extraction_threshold=1,
        miss_reply=miss_reply,
    )
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="答"))

    async def _stream(**kwargs):
        context["stream_kwargs"] = kwargs
        yield {"type": "token", "content": "答"}

    agent.process_message_stream = MagicMock(side_effect=_stream)
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
    resolve_identity = AsyncMock()
    resolve_identity.execute = AsyncMock(return_value="profile-1")
    load_memory = AsyncMock()
    load_memory.execute = AsyncMock(
        return_value=SimpleNamespace(has_memory=True, formatted_prompt="記憶")
    )
    extract_memory = AsyncMock()
    context.update(
        agent=agent, query_rag=query_rag, classifier=classifier,
        resolve_identity=resolve_identity,
    )
    uc = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        intent_classifier=classifier,
        worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
        resolve_identity_use_case=resolve_identity,
        load_memory_use_case=load_memory,
        extract_memory_use_case=extract_memory,
    )
    _spy_trace(context, uc)
    context["uc"] = uc


@given(parsers.parse('一個 mode 為 "{mode}" 且沒有 worker 的 bot，檢索分數 {score:g}'))
def bot_no_worker(context, mode, score):
    _setup_web(context, mode=mode, score=score)


@given(parsers.parse(
    '一個 mode 為 "{mode}" 且未命中話術為 "{miss}" 的 bot，檢索分數 {score:g}'
))
def bot_with_miss_reply(context, mode, miss, score):
    _setup_web(context, mode=mode, score=score, miss_reply=_text(miss))


@given(parsers.parse(
    '一個 mode 為 "{mode}" 且 rerank 開啟、記憶開啟、沒有 worker 的 bot，'
    "檢索分數 {score:g}"
))
def bot_rerank_memory(context, mode, score):
    _setup_web(context, mode=mode, score=score, rerank=True, memory=True)


def _command():
    # visitor_id + identity_source 讓記憶 load / extract 路徑有機會被觸發
    return SendMessageCommand(
        tenant_id="t1", bot_id="bot-kb", message="板橋店有快剪嗎",
        visitor_id="v-1", identity_source="widget",
    )


@when("以 web 送出訊息")
def send_web(context):
    context["response"] = _run(context["uc"].execute(_command()))


@when("以 web 串流送出訊息")
def send_web_stream(context):
    async def _collect():
        events = []
        async for ev in context["uc"].execute_stream(_command()):
            events.append(ev)
        return events

    context["events"] = _run(_collect())


@then("Agent 應以空工具集被呼叫")
def agent_no_tools(context):
    context["agent"].process_message.assert_awaited_once()
    kwargs = context["agent"].process_message.call_args.kwargs
    assert kwargs["enabled_tools"] == [], kwargs["enabled_tools"]
    assert not kwargs.get("mcp_servers")


@then("串流 Agent 應以空工具集被呼叫")
def stream_agent_no_tools(context):
    assert context["stream_kwargs"]["enabled_tools"] == []


@then("Agent 不應被呼叫")
def agent_not_called(context):
    context["agent"].process_message.assert_not_awaited()


@then("串流 Agent 不應被呼叫")
def stream_agent_not_called(context):
    context["agent"].process_message_stream.assert_not_called()


@then(parsers.parse("共用檢索應被呼叫 {n:d} 次"))
def retrieve_called(context, n):
    assert context["query_rag"].retrieve.await_count == n


@then("意圖分類器不應被呼叫")
def classifier_not_called(context):
    context["classifier"].classify_sanitize.assert_not_awaited()
    context["classifier"].classify.assert_not_awaited()


@then(parsers.parse('回覆內容應為 "{text}"'))
def reply_is(context, text):
    assert context["response"].answer == text, context["response"].answer


@then("回覆內容應為系統預設未命中話術")
def reply_is_default_miss(context):
    assert context["response"].answer == DEFAULT_MISS_REPLY


@then(parsers.parse('trace 應含 "{node_type}" 節點'))
def trace_has_node(context, node_type):
    types = [n.get("node_type") for n in context.get("trace_nodes", [])]
    assert node_type in types, types


@then(parsers.parse("共用檢索應以 rerank_enabled {value} 被呼叫"))
def retrieve_rerank(context, value):
    cmd = context["query_rag"].retrieve.call_args.args[0]
    assert cmd.rerank_enabled is (value == "true")


@then("記憶抽取不應被排程")
def memory_not_scheduled(context):
    # kb 模式：記憶 load 與 extract 都不得觸發（identity 解析是兩者的共同入口）
    context["resolve_identity"].execute.assert_not_awaited()


@then(parsers.parse('串流內容應為 "{text}"'))
def stream_content_is(context, text):
    content = "".join(
        e.get("content", "") for e in context["events"] if e.get("type") == "token"
    )
    assert content == text, content
    assert context["events"][-1]["type"] == "done"


# ── LINE ──


def _setup_line(context, *, mode, score, miss_reply=""):
    bot = Bot(
        tenant_id="t1", name="KB", line_channel_secret="s",
        line_channel_access_token="t", knowledge_base_ids=["kb-1"], mode=mode,
        miss_reply=miss_reply,
    )
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="有"))
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(score),
    ))
    context.update(agent=agent, query_rag=query_rag, line_service=line_service)
    context["line_uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=bot_repo, line_service_factory=factory,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )


@given(parsers.parse(
    'LINE 用例與 mode 為 "{mode}" 且沒有 worker 的 bot，檢索分數 {score:g}'
))
def line_setup(context, mode, score):
    _setup_line(context, mode=mode, score=score)


@given(parsers.parse(
    'LINE 用例與 mode 為 "{mode}" 且未命中話術為 "{miss}" 的 bot，檢索分數 {score:g}'
))
def line_setup_miss(context, mode, miss, score):
    _setup_line(context, mode=mode, score=score, miss_reply=_text(miss))


@when("系統處理一則 LINE 訊息")
def line_process(context):
    body = json.dumps({"events": [{
        "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
        "message": {"type": "text", "text": "板橋店有快剪嗎"},
        "timestamp": 1700000000000, "webhookEventId": "evt-kb-1",
    }]})
    _run(context["line_uc"].execute_for_bot("shop", body, "sig"))


@then("LINE Agent 應以空工具集被呼叫")
def line_agent_no_tools(context):
    context["agent"].process_message.assert_awaited_once()
    assert context["agent"].process_message.call_args.kwargs["enabled_tools"] == []


@then("LINE Agent 不應被呼叫")
def line_agent_not_called(context):
    context["agent"].process_message.assert_not_awaited()


@then(parsers.parse('LINE 回覆文字應為 "{text}"'))
def line_reply_is(context, text):
    call = context["line_service"].reply_with_quick_reply.call_args
    assert call.args[1] == text, call.args[1]


# ── bot mode 值域 ──


@given("一個既有的 bot")
def existing_bot(context):
    bot = Bot(id=BotId(value="bot-m"), tenant_id="t1", name="M")
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=bot)
    repo.save = AsyncMock()
    context["bot"] = bot
    context["bot_uc"] = UpdateBotUseCase(bot_repository=repo)


@when(parsers.parse('將 bot mode 更新為 "{mode}"'))
def update_mode(context, mode):
    try:
        _run(context["bot_uc"].execute(UpdateBotCommand(bot_id="bot-m", mode=mode)))
        context["outcome"] = "saved"
    except (ValidationError, ValueError):
        context["outcome"] = "error"


@then(parsers.parse("結果應為 {outcome}"))
def mode_outcome(context, outcome):
    assert context["outcome"] == outcome


# ── 快照 ──


@given(parsers.parse('一個 mode 為 "{mode}" 的 bot 實體'))
def bot_entity(context, mode):
    context["bot"] = Bot(tenant_id="t1", name="S", mode=mode)


@when(parsers.parse('取快照後把未命中話術改為 "{text}" 再取一次快照'))
def snapshot_twice(context, text):
    context["snap_a"] = take_snapshot(context["bot"])
    context["bot"].miss_reply = text
    context["snap_b"] = take_snapshot(context["bot"])


@then(parsers.parse('快照應含 "{field}" 且 diff 應列出 "{changed}"'))
def snapshot_has_field(context, field, changed):
    assert field in context["snap_a"]
    assert "output_format" in context["snap_a"]
    assert changed in diff_snapshots(context["snap_a"], context["snap_b"])
