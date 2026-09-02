"""線上 LLM 自評下線 BDD Step Definitions（Issue #59）"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId

scenarios("unit/observability/online_eval_retired.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context(monkeypatch):
    enqueued: list[tuple] = []

    async def _fake_enqueue(*args, **kwargs):
        enqueued.append(args)

    import src.infrastructure.queue.arq_pool as arq_pool

    monkeypatch.setattr(arq_pool, "enqueue", _fake_enqueue)
    return {"enqueued": enqueued}


@given(parsers.parse('一個 eval_depth 為 "{depth}" 的 bot'))
def bot_with_eval(context, depth):
    bot = Bot(
        id=BotId(value="bot-eval"),
        tenant_id="t1",
        name="eval bot",
        base_prompt="提示詞",
        eval_depth=depth,
    )
    agent = AsyncMock()
    agent.process_message.return_value = AgentResponse(answer="回答")

    async def _stream(**_kwargs):
        yield {"type": "token", "content": "回答"}
        yield {"type": "done"}

    agent.process_message_stream = _stream
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None
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
    context["command"] = SendMessageCommand(
        tenant_id="t1", bot_id="bot-eval", message="測試",
    )


@when("以非串流方式送出訊息")
def send_non_stream(context):
    _run(context["uc"].execute(context["command"]))


@when("以串流方式送出訊息")
def send_stream(context):
    async def _consume():
        async for _ in context["uc"].execute_stream(context["command"]):
            pass

    _run(_consume())


@then(parsers.parse('不應 enqueue 任何 "{task}" 任務'))
def no_task_enqueued(context, task):
    names = [args[0] for args in context["enqueued"] if args]
    assert task not in names, names


@when("建立一個未指定 eval_depth 的 Bot 實體")
def build_default_bot(context):
    context["bot"] = Bot(tenant_id="t1", name="b")


@then(parsers.parse('該 Bot 的 eval_depth 應為 "{depth}"'))
def bot_eval_depth(context, depth):
    assert context["bot"].eval_depth == depth


@when("讀取 worker 的任務註冊表")
def read_worker_functions(context):
    from src.worker import WorkerSettings

    context["functions"] = [f.name for f in WorkerSettings.functions]


@then(parsers.parse('註冊表不應包含 "{name}"'))
def functions_exclude(context, name):
    assert name not in context["functions"], context["functions"]
