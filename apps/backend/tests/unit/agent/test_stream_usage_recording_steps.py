"""Issue #96：串流記帳移入 use case + shielded 收尾（Repository / agent 全 mock）。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.direct_retrieval_service import DirectRetrievalService
from src.application.agent.intent_classifier import ClassifyOutcome
from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.rag.query_rag_use_case import RetrieveResult
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.mode_presets import preset_values
from src.domain.bot.value_objects import BotId
from src.domain.rag.value_objects import Source, TokenUsage

scenarios("unit/agent/stream_usage_recording.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {"errors": []}


@given("一個會串出 token 與 usage 的 kb bot")
def kb_bot(ctx):
    bot = Bot(
        id=BotId(value="bot-kb"), tenant_id="t1", name="KB",
        knowledge_base_ids=["kb-1"], mode="kb", memory_extraction_threshold=1,
    )
    for k, v in preset_values("kb").items():
        setattr(bot, k, v)
    usage = TokenUsage(model="m", input_tokens=10, output_tokens=5, estimated_cost=0.0)

    agent = AsyncMock()
    agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="答", usage=usage)
    )

    async def _stream(**kwargs):
        yield {"type": "token", "content": "答"}
        ctx["first_token"].set()
        await asyncio.sleep(0.05)
        yield {"type": "token", "content": "案"}
        yield {
            "type": "usage", "model": "m", "input_tokens": 10, "output_tokens": 5,
            "total_tokens": 15, "estimated_cost": 0.0,
        }

    agent.process_message_stream = MagicMock(side_effect=_stream)

    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None

    async def _save(conversation):
        ctx["save_started"].set()
        await asyncio.sleep(ctx.get("save_delay", 0))
        ctx["saved"] = conversation

    conv_repo.save = AsyncMock(side_effect=_save)
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=[])
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(
        return_value=ClassifyOutcome(worker=None, query="", is_attack=False)
    )
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"],
        sources=[
            Source(document_name="FAQ", content_snippet="x", score=0.9, chunk_id="c-1")
        ],
    ))
    record = AsyncMock()
    record.execute = AsyncMock()
    ctx.update(record=record, conv_repo=conv_repo, first_token=asyncio.Event(),
               save_started=asyncio.Event())
    ctx["uc"] = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        intent_classifier=classifier,
        worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
        record_usage_use_case=record,
    )


@given("儲存對話需要 0.2 秒")
def slow_save(ctx):
    ctx["save_delay"] = 0.2


@given("record_usage 會拋例外")
def record_raises(ctx):
    ctx["record"].execute = AsyncMock(side_effect=RuntimeError("ledger down"))


def _command(identity_source="web", request_type="chat_web", run_id="run-1"):
    return SendMessageCommand(
        tenant_id="t1", bot_id="bot-kb", message="板橋店有快剪嗎",
        identity_source=identity_source,
        usage_request_type=request_type, usage_run_id=run_id,
    )


async def _consume(ctx, command, cancel_when=None):
    """以 anyio task group 驅動串流（Starlette StreamingResponse 同款取消機制）。"""
    events: list[dict] = []
    # Event 必須綁在執行中的 loop 上
    ctx["first_token"] = asyncio.Event()
    ctx["save_started"] = asyncio.Event()

    async def producer():
        try:
            async for ev in ctx["uc"].execute_stream(command):
                events.append(ev)
        except asyncio.CancelledError:
            ctx["cancelled"] = True
            raise
        except Exception as e:  # noqa: BLE001
            ctx["errors"].append(e)

    async with anyio.create_task_group() as tg:
        tg.start_soon(producer)
        if cancel_when is not None:
            await ctx[cancel_when].wait()
            tg.cancel_scope.cancel()
    ctx["events"] = events


@when("以 web 串流送出訊息並完整讀完")
def stream_full(ctx):
    _run(_consume(ctx, _command()))


@when("以 web 串流送出訊息並在儲存對話進行中斷線")
def stream_cancel_in_save(ctx):
    _run(_consume(ctx, _command(), cancel_when="save_started"))


@when("以 web 串流送出訊息並在第一個 token 後斷線")
def stream_cancel_in_generation(ctx):
    _run(_consume(ctx, _command(), cancel_when="first_token"))


@when("以 web 非串流送出訊息")
def non_stream(ctx):
    ctx["response"] = _run(ctx["uc"].execute(_command()))


@when(parsers.parse(
    '以 identity_source "{src}" 且未指定 request_type 串流送出訊息並完整讀完'
))
def stream_widget_default(ctx, src):
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-kb", message="板橋店有快剪嗎",
        identity_source=src, visitor_id="v-1",
    )
    _run(_consume(ctx, cmd))


@then(parsers.parse("record_usage 被呼叫 {n:d} 次"))
def record_calls(ctx, n):
    assert ctx["record"].execute.await_count == n


@then(parsers.parse("record_usage 被呼叫 {n:d} 次且 usage 標記 estimated"))
def record_calls_estimated(ctx, n):
    assert ctx["record"].execute.await_count == n
    usage = ctx["record"].execute.await_args.kwargs["usage"]
    assert usage.estimated is True and usage.output_tokens > 0


@then(parsers.parse(
    '記帳帶有 message_id、request_type "{rt}" 與 run_id "{run}"'
))
def record_kwargs(ctx, rt, run):
    kw = ctx["record"].execute.await_args.kwargs
    assert kw["message_id"], kw
    assert kw["request_type"] == rt and kw["run_id"] == run
    assert kw["tenant_id"] == "t1" and kw["bot_id"] == "bot-kb"
    assert isinstance(kw["usage"], TokenUsage) and kw["usage"].total_tokens == 15


@then(parsers.parse('記帳的 request_type 為 "{rt}"'))
def record_rt(ctx, rt):
    assert ctx["record"].execute.await_args.kwargs["request_type"] == rt


@then("對話已儲存")
def saved(ctx):
    assert ctx.get("saved") is not None
    assert len(ctx["saved"].messages) == 2


@then("對話未儲存")
def not_saved(ctx):
    assert ctx.get("saved") is None


@then("只發生取消，沒有其他例外")
def only_cancel(ctx):
    assert ctx.get("cancelled") is True
    assert ctx["errors"] == []


@then("沒有其他例外")
def no_other_errors(ctx):
    # 收尾在 shielded scope 內完成後，若剩餘程式已無 await 檢查點，
    # 取消可能根本不會被觀察到（串流正常結束）；兩種結果都可接受。
    assert ctx["errors"] == []


@then("事件序列以 done 結尾")
def ends_with_done(ctx):
    assert ctx["events"][-1]["type"] == "done"
