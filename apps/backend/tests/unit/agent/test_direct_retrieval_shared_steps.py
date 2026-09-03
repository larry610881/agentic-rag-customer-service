"""快速道共用管線 BDD Step Definitions（Issue #61）"""

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
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import RetrieveResult
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId
from src.domain.bot.worker_config import WorkerConfig
from src.domain.rag.value_objects import Source
from src.infrastructure.llm.openai_llm_service import (
    normalize_reasoning_effort,
    reasoning_effort_allowed,
)

scenarios("unit/agent/direct_retrieval_shared.feature")


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
        document_name="門市 FAQ", content_snippet="板橋店 2 樓設有快剪",
        score=score, chunk_id="c-1",
    )]


def _setup_web(
    context, *, direct: bool, score: float = 0.85, rerank: bool = False,
    mode: str = "deep",
):
    bot = Bot(
        id=BotId(value="bot-dr"), tenant_id="t1", name="DR", base_prompt="p",
        knowledge_base_ids=["kb-faq"], rerank_enabled=rerank, mode=mode,
    )
    worker = WorkerConfig(
        bot_id="bot-dr", name="門市服務查詢", worker_prompt="你是門市客服",
        knowledge_base_ids=["kb-faq"], direct_retrieval=direct,
        enabled_tools=["rag_query"],
    )
    agent = AsyncMock()
    agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="板橋店 2 樓有快剪。")
    )

    async def _stream(**_kwargs):
        yield {"type": "token", "content": "板橋店"}
        yield {"type": "done"}

    agent.process_message_stream = _stream
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=[worker])
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(
        return_value=ClassifyOutcome(
            worker=worker, query="板橋店 快剪", is_attack=False
        )
    )
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪理髮店，營業至 21:00"], sources=_sources(score),
    ))
    context.update(agent=agent, query_rag=query_rag)
    context["uc"] = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        intent_classifier=classifier,
        worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )


@given(parsers.parse("一個開啟直接檢索的 Worker 且共用檢索結果分數為 {score:g}"))
def worker_direct(context, score):
    _setup_web(context, direct=True, score=score)


@given("一個未開啟直接檢索的 Worker")
def worker_not_direct(context):
    _setup_web(context, direct=False)


@given("一個 mode 為 fast 且 bot 開啟 rerank 的 Worker")
def worker_direct_rerank(context):
    _setup_web(context, direct=True, rerank=True, mode="fast")


@when(parsers.parse('以來源 "{source}" 以非串流方式送出訊息'))
def send(context, source):
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-dr", message="板橋店有快剪嗎",
        identity_source=source,
    )
    context["response"] = _run(context["uc"].execute(cmd))


@when("以串流方式送出訊息並收集事件")
def send_stream(context):
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-dr", message="板橋店有快剪嗎"
    )
    events = []
    context["stream_kwargs"] = {}
    original = context["agent"].process_message_stream

    async def _spy(**kwargs):
        context["stream_kwargs"] = kwargs
        async for ev in original(**kwargs):
            yield ev

    context["agent"].process_message_stream = _spy

    async def _consume():
        async for ev in context["uc"].execute_stream(cmd):
            events.append(ev)

    _run(_consume())
    context["events"] = events


@then("Agent 應以 max_tool_calls 1 且無檢索工具被呼叫")
def agent_fast(context):
    kwargs = context["agent"].process_message.call_args.kwargs
    assert kwargs["max_tool_calls"] == 1
    assert "rag_query" not in (kwargs.get("enabled_tools") or [])


@then(parsers.parse('生成 Prompt 應包含 "{text}"'))
def prompt_contains(context, text):
    kwargs = context["agent"].process_message.call_args.kwargs
    assert text in (kwargs["system_prompt"] or "")


@then(parsers.parse('回應來源應含 {n:d} 筆且 chunk_id 為 "{cid}"'))
def response_sources(context, n, cid):
    sources = context["response"].sources
    assert len(sources) == n and sources[0].chunk_id == cid


@then("Agent 串流應以 max_tool_calls 1 被呼叫")
def stream_fast(context):
    assert context["stream_kwargs"].get("max_tool_calls") == 1


@then(parsers.parse('事件中應含 {n:d} 個 sources 事件且 chunk_id 為 "{cid}"'))
def stream_sources_event(context, n, cid):
    src_events = [e for e in context["events"] if e.get("type") == "sources"]
    assert len(src_events) == n, [e.get("type") for e in context["events"]]
    first = src_events[0]["sources"][0]
    chunk_id = first["chunk_id"] if isinstance(first, dict) else first.chunk_id
    assert chunk_id == cid


@then("Agent 應以完整工具模式被呼叫")
def agent_full(context):
    kwargs = context["agent"].process_message.call_args.kwargs
    assert kwargs["max_tool_calls"] != 1
    assert "rag_query" in (kwargs.get("enabled_tools") or ["rag_query"])


@then("共用檢索不應被呼叫")
def retrieve_not_called(context):
    context["query_rag"].retrieve.assert_not_awaited()


@then("共用檢索應以 rerank_enabled false 被呼叫")
def retrieve_no_rerank(context):
    cmd = context["query_rag"].retrieve.call_args.args[0]
    assert cmd.rerank_enabled is False


@then(parsers.parse("共用檢索應被呼叫 {n:d} 次"))
def retrieve_called(context, n):
    assert context["query_rag"].retrieve.await_count == n


# ── LINE ──


@given("LINE 用例以共用檢索服務建構且 Worker 開啟直接檢索")
def line_setup(context):
    bot = Bot(
        tenant_id="tenant-dr", name="DR Bot", line_channel_secret="s",
        line_channel_access_token="t", knowledge_base_ids=["kb-faq"],
    )
    worker = WorkerConfig(
        bot_id=bot.id.value, name="門市服務查詢", worker_prompt="你是門市客服",
        knowledge_base_ids=["kb-faq"], direct_retrieval=True,
    )
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="有"))
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=[worker])
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(
        return_value=ClassifyOutcome(worker=worker, query="", is_attack=False)
    )
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(0.9),
    ))
    context.update(agent=agent, query_rag=query_rag)
    context["line_uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=bot_repo, line_service_factory=factory,
        intent_classifier=classifier, worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )


@when("系統處理一則命中該 Worker 的 LINE 訊息")
def line_process(context):
    body = json.dumps({"events": [{
        "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
        "message": {"type": "text", "text": "板橋店有快剪嗎"},
        "timestamp": 1700000000000, "webhookEventId": "evt-dr-1",
    }]})
    _run(context["line_uc"].execute_for_bot("shop", body, "sig"))


@then("LINE Agent 應以 max_tool_calls 1 被呼叫")
def line_fast(context):
    kwargs = context["agent"].process_message.call_args.kwargs
    assert kwargs["max_tool_calls"] == 1


# ── Gemini ──


@when(parsers.parse('以模型 "{model}" 檢查 reasoning_effort "{effort}"'))
def check_effort(context, model, effort):
    context["allowed"] = reasoning_effort_allowed(model, effort)
    context["normalized"] = normalize_reasoning_effort(model, effort)


@then(parsers.parse('允許結果應為 {allowed} 且正規化值為 "{normalized}"'))
def effort_result(context, allowed, normalized):
    assert context["allowed"] is (allowed == "true")
    assert context["normalized"] == normalized
