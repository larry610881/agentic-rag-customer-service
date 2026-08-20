"""Config Override 影子執行與 test-mode 隔離 BDD Step Definitions"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.conversation.repository import ConversationRepository
from src.domain.prompt_gate.config_snapshot import take_snapshot
from src.domain.shared.exceptions import DomainException

scenarios("unit/prompt_gate/shadow_execution.feature")

BOT_ID = "bot-1"
TENANT = "t1"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def bot():
    return Bot(
        id=BotId(value=BOT_ID),
        tenant_id=TENANT,
        name="測試 bot",
        base_prompt="線上提示詞",
        memory_enabled=True,
        memory_extraction_threshold=1,
        eval_depth="L1+L2",
    )


@pytest.fixture
def deps(bot, monkeypatch):
    agent_service = AsyncMock()
    agent_service.process_message.return_value = AgentResponse(
        answer="模型回答"
    )
    conv_repo = AsyncMock(spec=ConversationRepository)
    conv_repo.find_by_id.return_value = None
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id.return_value = bot
    sys_prompt_repo = AsyncMock()
    sys_prompt_repo.get.return_value = SimpleNamespace(
        system_prompt="系統預設提示詞"
    )
    eval_uc = AsyncMock()

    enqueued: list[tuple] = []

    async def _fake_enqueue(*args, **kwargs):
        enqueued.append(args)

    import src.infrastructure.queue.arq_pool as arq_pool

    monkeypatch.setattr(arq_pool, "enqueue", _fake_enqueue)

    return SimpleNamespace(
        agent_service=agent_service,
        conv_repo=conv_repo,
        bot_repo=bot_repo,
        sys_prompt_repo=sys_prompt_repo,
        eval_uc=eval_uc,
        enqueued=enqueued,
    )


def _make_use_case(deps, prompt_guard=None):
    return SendMessageUseCase(
        agent_service=deps.agent_service,
        conversation_repository=deps.conv_repo,
        bot_repository=deps.bot_repo,
        system_prompt_config_repository=deps.sys_prompt_repo,
        rag_evaluation_use_case=deps.eval_uc,
        extract_memory_use_case=AsyncMock(),
        prompt_guard=prompt_guard,
        trace_session_factory=None,
    )


@given("一個 base_prompt 為 \"線上提示詞\" 的 bot 與含 \"草稿提示詞\" 的 override 快照")
def override_snapshot(context, bot, deps):
    snap = take_snapshot(bot)
    snap["base_prompt"] = "草稿提示詞"
    context["override"] = snap
    context["uc"] = _make_use_case(deps)


@given("一個屬於其他租戶的 bot")
def foreign_bot(context, bot, deps):
    bot.tenant_id = "other-tenant"
    context["override"] = {"base_prompt": "任意"}
    context["uc"] = _make_use_case(deps)


@given("一個正常設定的 bot")
def normal_bot(context, deps):
    context["override"] = None
    context["uc"] = _make_use_case(deps)


@given("一個正常設定的 bot 且 guard 會攔截輸入")
def bot_with_blocking_guard(context, deps):
    guard = AsyncMock()
    guard.check_input.return_value = SimpleNamespace(
        passed=False,
        blocked_response="很抱歉，這個問題我無法協助",
        rule_matched="injection",
    )
    context["override"] = None
    context["uc"] = _make_use_case(deps, prompt_guard=guard)


@given("一個開啟 memory 與 eval_depth 的 bot")
def bot_with_memory_eval(context, deps):
    # bot fixture 已開 memory_enabled + eval_depth
    context["override"] = None
    context["uc"] = _make_use_case(deps)


@given("一個正常設定的 bot 與兩則 history_override 訊息")
def bot_with_history(context, deps):
    context["override"] = None
    context["history"] = [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "第一答"},
    ]
    context["uc"] = _make_use_case(deps)


def _command(context, **kw):
    return SendMessageCommand(
        tenant_id=TENANT,
        bot_id=BOT_ID,
        message="測試訊息",
        config_override=context.get("override"),
        test_mode=True,
        history_override=context.get("history"),
        **kw,
    )


@when("以 config_override 執行影子對話")
def run_with_override(context):
    try:
        context["result"] = _run(context["uc"].execute(_command(context)))
    except DomainException as exc:
        context["error"] = exc


@when("以 test_mode 執行影子對話")
def run_test_mode(context):
    context["result"] = _run(context["uc"].execute(_command(context)))


@when("以 test_mode 與 history_override 執行影子對話")
def run_with_history(context):
    context["result"] = _run(context["uc"].execute(_command(context)))


@then("agent 收到的 system prompt 含 \"草稿提示詞\"")
def verify_prompt_overridden(context, deps):
    kwargs = deps.agent_service.process_message.call_args.kwargs
    assert "草稿提示詞" in (kwargs["system_prompt"] or "")
    assert "線上提示詞" not in (kwargs["system_prompt"] or "")


@then("bot repository 未被呼叫 save")
def verify_bot_not_saved(deps):
    assert deps.bot_repo.save.await_count == 0


@then("執行被拒絕（找不到 bot）")
def verify_foreign_rejected(context):
    assert isinstance(context["error"], DomainException)


@then("conversation repository 未被呼叫 save")
def verify_conv_not_saved(deps):
    assert deps.conv_repo.save.await_count == 0


@then("回應為 guard 攔截訊息")
def verify_guard_response(context):
    assert context["result"].guard_blocked == "input"
    assert "無法協助" in context["result"].answer


@then("未 enqueue extract_memory 與 run_evaluation")
def verify_no_background_jobs(deps):
    assert deps.enqueued == []


@then("回應含 trace_id 與 trace_nodes")
def verify_trace_returned(context):
    assert context["result"].trace_id
    assert context["result"].trace_nodes is not None


@then("trace 未被持久化")
def verify_trace_not_persisted(context):
    # trace_session_factory=None + persist=False：沒有任何 DB 寫入路徑；
    # 且 ContextVar 已被 finish() 清空（不殘留到下個 request）
    from src.infrastructure.observability.agent_trace_collector import (
        AgentTraceCollector,
    )

    assert AgentTraceCollector.current() is None


@then("agent 收到的對話歷史即為 override 內容")
def verify_history_used(deps):
    kwargs = deps.agent_service.process_message.call_args.kwargs
    ctx = kwargs.get("history_context") or ""
    assert "第一句" in ctx
    assert "第一答" in ctx


@then("conversation repository 未被查詢歷史")
def verify_no_history_query(deps):
    assert deps.conv_repo.find_by_id.await_count == 0
