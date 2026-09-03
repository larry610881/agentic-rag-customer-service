"""快速道 profile BDD Step Definitions（Issue #66）"""

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
from src.application.bot.worker_use_cases import (
    CreateWorkerCommand,
    CreateWorkerUseCase,
    UpdateWorkerCommand,
    UpdateWorkerUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import RetrieveResult
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId
from src.domain.bot.worker_config import WorkerConfig
from src.domain.prompt_gate.config_snapshot import diff_snapshots, take_snapshot
from src.domain.rag.value_objects import Source
from src.domain.shared.exceptions import ValidationError

scenarios("unit/agent/fast_lane_profile.feature")


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


def _setup_web(context, *, mode, score, rerank=False, worker_direct=None):
    bot = Bot(
        id=BotId(value="bot-p"), tenant_id="t1", name="P", base_prompt="p",
        knowledge_base_ids=["kb-1"], rerank_enabled=rerank, mode=mode,
    )
    workers = []
    if worker_direct is not None:
        workers = [WorkerConfig(
            bot_id="bot-p", name="門市", worker_prompt="你是門市客服",
            knowledge_base_ids=["kb-1"], direct_retrieval=worker_direct,
            enabled_tools=["rag_query"],
        )]
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="答"))
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=workers)
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(return_value=ClassifyOutcome(
        worker=workers[0] if workers else None, query="", is_attack=False,
    ))
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(score),
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


@given(parsers.parse('一個 mode 為 "{mode}" 且沒有 worker 的 bot，檢索分數 {score:g}'))
def bot_no_worker(context, mode, score):
    _setup_web(context, mode=mode, score=score)


@given(parsers.parse(
    '一個 mode 為 "{mode}" 且 rerank 開啟、沒有 worker 的 bot，檢索分數 {score:g}'
))
def bot_rerank_no_worker(context, mode, score):
    _setup_web(context, mode=mode, score=score, rerank=True)


@given(parsers.parse(
    '一個 mode 為 "{mode}" 且 rerank 開啟、worker 開啟直接檢索的 bot，'
    '檢索分數 {score:g}'
))
def bot_rerank_worker_direct(context, mode, score):
    _setup_web(context, mode=mode, score=score, rerank=True, worker_direct=True)


@when("以 web 送出訊息")
def send_web(context):
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-p", message="板橋店有快剪嗎"
    )
    context["response"] = _run(context["uc"].execute(cmd))


@then(parsers.parse("Agent 應以 max_tool_calls {n:d} 被呼叫"))
def agent_max_tool_calls(context, n):
    kwargs = context["agent"].process_message.call_args.kwargs
    assert kwargs["max_tool_calls"] == n, kwargs["max_tool_calls"]


@then(parsers.parse("共用檢索應被呼叫 {n:d} 次"))
def retrieve_called(context, n):
    assert context["query_rag"].retrieve.await_count == n


@then("共用檢索不應被呼叫")
def retrieve_not_called(context):
    context["query_rag"].retrieve.assert_not_awaited()


@then(parsers.parse("共用檢索應以 rerank_enabled {value} 被呼叫"))
def retrieve_rerank(context, value):
    cmd = context["query_rag"].retrieve.call_args.args[0]
    assert cmd.rerank_enabled is (value == "true")


# ── LINE ──


@given(parsers.parse('LINE 用例與 mode 為 "{mode}" 且沒有 worker 的 bot'))
def line_setup(context, mode):
    bot = Bot(
        tenant_id="t1", name="P", line_channel_secret="s",
        line_channel_access_token="t", knowledge_base_ids=["kb-1"], mode=mode,
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
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(0.9),
    ))
    context.update(agent=agent, query_rag=query_rag)
    context["line_uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=bot_repo, line_service_factory=factory,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )


@when("系統處理一則 LINE 訊息")
def line_process(context):
    body = json.dumps({"events": [{
        "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
        "message": {"type": "text", "text": "板橋店有快剪嗎"},
        "timestamp": 1700000000000, "webhookEventId": "evt-fp-1",
    }]})
    _run(context["line_uc"].execute_for_bot("shop", body, "sig"))


@then(parsers.parse("LINE Agent 應以 max_tool_calls {n:d} 被呼叫"))
def line_agent_max(context, n):
    assert context["agent"].process_message.call_args.kwargs["max_tool_calls"] == n


# ── worker CRUD ──


@given("worker 用例")
def worker_ucs(context):
    store: dict = {}
    repo = AsyncMock()

    async def _save(w):
        store[w.id] = w

    async def _find(wid):
        return store.get(wid)

    repo.save = AsyncMock(side_effect=_save)
    repo.find_by_id = AsyncMock(side_effect=_find)
    context["create_uc"] = CreateWorkerUseCase(repo=repo)
    context["update_uc"] = UpdateWorkerUseCase(repo=repo)
    context["store"] = store


@when("建立 worker 時 direct_retrieval 為 true，再更新為 false")
def worker_lifecycle(context):
    w = _run(context["create_uc"].execute(CreateWorkerCommand(
        bot_id="bot-p", name="門市", direct_retrieval=True,
    )))
    context["after_create"] = context["store"][w.id].direct_retrieval
    _run(context["update_uc"].execute(UpdateWorkerCommand(
        worker_id=w.id, direct_retrieval=False,
    )))
    context["after_update"] = context["store"][w.id].direct_retrieval


@then("儲存的 worker direct_retrieval 應依序為 true 與 false")
def worker_flags(context):
    assert context["after_create"] is True
    assert context["after_update"] is False


# ── bot mode ──


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
        context["saved_mode"] = context["bot"].mode
    except (ValidationError, ValueError):
        context["outcome"] = "error"


@then(parsers.parse("結果應為 {outcome}"))
def mode_outcome(context, outcome):
    assert context["outcome"] == outcome


@given(parsers.parse('一個 mode 為 "{mode}" 的 bot 實體'))
def bot_entity(context, mode):
    context["bot"] = Bot(tenant_id="t1", name="S", mode=mode)


@when(parsers.parse('取快照後把 mode 改為 "{mode}" 再取一次快照'))
def snapshot_twice(context, mode):
    context["snap_a"] = take_snapshot(context["bot"])
    context["bot"].mode = mode
    context["snap_b"] = take_snapshot(context["bot"])


@then(parsers.parse('快照應含 "{field}" 且 diff 應列出 "{changed}"'))
def snapshot_has_mode(context, field, changed):
    assert field in context["snap_a"]
    assert changed in diff_snapshots(context["snap_a"], context["snap_b"])
