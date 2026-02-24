"""對話歷史策略 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.history_strategy import HistoryStrategyConfig
from src.domain.conversation.value_objects import ConversationId, MessageId
from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.infrastructure.conversation.full_history_strategy import (
    FullHistoryStrategy,
)
from src.infrastructure.conversation.sliding_window_strategy import (
    SlidingWindowStrategy,
)
from src.infrastructure.conversation.summary_recent_strategy import (
    SummaryRecentStrategy,
)

scenarios("unit/conversation/conversation_history_strategy.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_messages(count: int) -> list[Message]:
    msgs: list[Message] = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"訊息{i + 1}" if role == "user" else f"回覆{i + 1}"
        msgs.append(
            Message(
                id=MessageId(value=f"msg-{i}"),
                conversation_id="conv-test",
                role=role,
                content=content,
            )
        )
    return msgs


@pytest.fixture
def context():
    return {}


# --- Given ---


@given(parsers.parse("一段包含 {count:d} 條訊息的對話歷史"))
def setup_history(context, count):
    context["messages"] = _make_messages(count)


@given("一段空的對話歷史")
def setup_empty_history(context):
    context["messages"] = []


@given("一個注入 sliding_window 策略的 SendMessageUseCase")
def setup_use_case_with_strategy(context):
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(
            answer="測試回應",
            tool_calls=[
                {"tool_name": "rag_query", "reasoning": "知識型問題"}
            ],
            conversation_id="temp",
            usage=TokenUsage.zero("fake"),
        )
    )
    mock_repo = AsyncMock()
    mock_repo.save = AsyncMock()

    strategy = SlidingWindowStrategy()

    context["mock_agent"] = mock_agent
    context["mock_repo"] = mock_repo
    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_repo,
        history_strategy=strategy,
    )


@given("一段包含歷史訊息的對話")
def setup_conversation_with_history(context):
    conv = Conversation(
        id=ConversationId(value="conv-strategy"),
        tenant_id="tenant-001",
    )
    conv.add_message("user", "你好")
    conv.add_message("assistant", "您好，很高興為您服務")
    conv.add_message("user", "我要退貨")
    conv.add_message("assistant", "好的，請提供訂單號")
    context["conversation"] = conv
    context["mock_repo"].find_by_id = AsyncMock(return_value=conv)


# --- When ---


@when("使用 full 策略處理歷史")
def process_with_full(context):
    strategy = FullHistoryStrategy()
    context["result"] = _run(
        strategy.process(context["messages"])
    )


@when(
    parsers.parse(
        "使用 sliding_window 策略處理歷史且 history_limit 為 {limit:d}"
    )
)
def process_with_sliding_window_limit(context, limit):
    strategy = SlidingWindowStrategy()
    config = HistoryStrategyConfig(history_limit=limit)
    context["result"] = _run(
        strategy.process(context["messages"], config)
    )


@when("使用 sliding_window 策略處理歷史")
def process_with_sliding_window(context):
    strategy = SlidingWindowStrategy()
    context["result"] = _run(
        strategy.process(context["messages"])
    )


@when(
    parsers.parse(
        "使用 summary_recent 策略處理歷史且 recent_turns 為 {turns:d}"
    )
)
def process_with_summary_recent(context, turns):
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            text="用戶詢問了退貨政策及訂單 ORD-123 的狀態",
            usage=TokenUsage.zero("fake"),
        )
    )
    strategy = SummaryRecentStrategy(llm_service=mock_llm)
    config = HistoryStrategyConfig(recent_turns=turns)
    context["result"] = _run(
        strategy.process(context["messages"], config)
    )
    context["recent_turns"] = turns


@when("使用者在該對話發送新訊息")
def send_message_with_strategy(context):
    context["response"] = _run(
        context["use_case"].execute(
            SendMessageCommand(
                tenant_id="tenant-001",
                kb_id="kb-001",
                message="訂單 ORD-123 的狀態是什麼",
                conversation_id="conv-strategy",
            )
        )
    )


# --- Then ---


@then(parsers.parse("respond_context 應包含全部 {count:d} 條訊息"))
def verify_full_context(context, count):
    result = context["result"]
    assert result.message_count == count
    for i in range(count):
        expected = f"訊息{i + 1}" if i % 2 == 0 else f"回覆{i + 1}"
        assert expected in result.respond_context


@then(parsers.parse('strategy_name 應為 "{name}"'))
def verify_strategy_name(context, name):
    assert context["result"].strategy_name == name


@then(parsers.parse("respond_context 應僅包含最後 {count:d} 條訊息"))
def verify_window_context(context, count):
    result = context["result"]
    assert result.message_count == count
    total = len(context["messages"])
    # Should contain the last N messages
    for i in range(total - count, total):
        content = f"訊息{i + 1}" if i % 2 == 0 else f"回覆{i + 1}"
        assert content in result.respond_context
    # Should NOT contain the message just before the window
    first_excluded_idx = total - count - 1
    if first_excluded_idx >= 0:
        excluded = (
            f"] 訊息{first_excluded_idx + 1}\n"
            if first_excluded_idx % 2 == 0
            else f"] 回覆{first_excluded_idx + 1}\n"
        )
        assert excluded not in result.respond_context


@then("respond_context 應包含對話摘要標記")
def verify_summary_marker(context):
    assert "[對話摘要]" in context["result"].respond_context


@then(parsers.parse("respond_context 應包含最近 {count:d} 條完整訊息"))
def verify_recent_messages(context, count):
    result = context["result"]
    total = len(context["messages"])
    for i in range(total - count, total):
        content = f"訊息{i + 1}" if i % 2 == 0 else f"回覆{i + 1}"
        assert content in result.respond_context


@then("respond_context 應為空字串")
def verify_empty_context(context):
    assert context["result"].respond_context == ""


@then(parsers.parse("message_count 應為 {count:d}"))
def verify_message_count(context, count):
    assert context["result"].message_count == count


@then("AgentService 應收到非空的 history_context")
def verify_history_context_passed(context):
    call_kwargs = context["mock_agent"].process_message.call_args
    hc = call_kwargs.kwargs.get("history_context", "")
    assert hc != "", f"history_context should not be empty, got: {hc!r}"


@then("AgentService 應收到非空的 router_context")
def verify_router_context_passed(context):
    call_kwargs = context["mock_agent"].process_message.call_args
    rc = call_kwargs.kwargs.get("router_context", "")
    assert rc != "", f"router_context should not be empty, got: {rc!r}"
