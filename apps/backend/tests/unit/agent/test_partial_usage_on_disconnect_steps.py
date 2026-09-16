"""Issue #99 一-2：生成中斷線的部分計費（estimated usage）。"""

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
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.mode_presets import preset_values
from src.domain.bot.value_objects import BotId
from src.domain.rag.value_objects import Source, TokenUsage

scenarios("unit/agent/partial_usage_on_disconnect.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {"errors": []}


@given("一個會串出 token 與 usage 的 kb bot 並注入估算器")
def kb_bot(ctx):
    bot = Bot(
        id=BotId(value="bot-kb"), tenant_id="t1", name="KB",
        knowledge_base_ids=["kb-1"], mode="kb", memory_extraction_threshold=1,
    )
    for k, v in preset_values("kb").items():
        setattr(bot, k, v)
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="答"))

    async def _stream(**kwargs):
        ctx["gen_started"].set()
        await asyncio.sleep(0.05)
        yield {"type": "token", "content": "答案第一段"}
        ctx["first_token"].set()
        await asyncio.sleep(0.05)
        yield {"type": "token", "content": "第二段"}
        yield {"type": "usage", "model": "m", "input_tokens": 10, "output_tokens": 5,
               "total_tokens": 15, "estimated_cost": 0.0}

    agent.process_message_stream = MagicMock(side_effect=_stream)
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None

    async def _save(conversation):
        ctx["saved"] = conversation

    conv_repo.save = AsyncMock(side_effect=_save)
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統提示")
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
    ctx.update(record=record, conv_repo=conv_repo)
    ctx["uc"] = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        intent_classifier=classifier,
        worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
        record_usage_use_case=record,
        token_estimator=lambda text: max(1, len(text) // 2),
    )


@given("record_usage 會拋例外")
def record_raises(ctx):
    ctx["record"].execute = AsyncMock(side_effect=RuntimeError("ledger down"))


def _command():
    return SendMessageCommand(
        tenant_id="t1", bot_id="bot-kb", message="板橋店有快剪嗎",
        identity_source="web", usage_request_type="chat_web",
    )


async def _consume(ctx, cancel_when):
    ctx["gen_started"] = asyncio.Event()
    ctx["first_token"] = asyncio.Event()

    async def producer():
        try:
            async for _ev in ctx["uc"].execute_stream(_command()):
                pass
        except asyncio.CancelledError:
            ctx["cancelled"] = True
            raise
        except Exception as e:  # noqa: BLE001
            ctx["errors"].append(e)

    async with anyio.create_task_group() as tg:
        tg.start_soon(producer)
        await ctx[cancel_when].wait()
        tg.cancel_scope.cancel()


@when("以 web 串流送出訊息並在第一個 token 後斷線")
def cancel_after_first_token(ctx):
    _run(_consume(ctx, "first_token"))


@when("以 web 串流送出訊息並在生成開始前斷線")
def cancel_before_generation(ctx):
    _run(_consume(ctx, "gen_started"))


@then(parsers.parse("record_usage 被呼叫 {n:d} 次"))
def record_calls(ctx, n):
    assert ctx["record"].execute.await_count == n


@then("記帳的 usage 標記 estimated 且 output_tokens 大於 0 且 input_tokens 大於 0")
def usage_estimated(ctx):
    usage = ctx["record"].execute.await_args.kwargs["usage"]
    assert isinstance(usage, TokenUsage)
    assert usage.estimated is True
    assert usage.output_tokens > 0 and usage.input_tokens > 0
    assert ctx["record"].execute.await_args.kwargs["message_id"] is None


@then("對話未儲存")
def not_saved(ctx):
    assert ctx.get("saved") is None


@then("只發生取消，沒有其他例外")
def only_cancel(ctx):
    assert ctx.get("cancelled") is True
    assert ctx["errors"] == []


# ── RecordUsage → UsageRecord.estimated ──


@given("一個 RecordUsageUseCase 與記憶體 usage repository")
def record_uc(ctx):
    repo = AsyncMock()
    ctx["saved_records"] = []

    async def save(record):
        ctx["saved_records"].append(record)

    repo.save = AsyncMock(side_effect=save)
    ctx["record_uc"] = RecordUsageUseCase(usage_repository=repo)


@when("以 estimated 的 TokenUsage 記帳")
def record_estimated(ctx):
    usage = TokenUsage(
        model="m", input_tokens=7, output_tokens=3, estimated_cost=0.001, estimated=True
    )
    _run(ctx["record_uc"].execute(tenant_id="t1", request_type="chat_web", usage=usage))


@then("儲存的 UsageRecord 標記 estimated")
def saved_estimated(ctx):
    assert len(ctx["saved_records"]) == 1
    assert ctx["saved_records"][0].estimated is True
