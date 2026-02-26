"""對話摘要 Redis 快取 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.conversation.entity import Message
from src.domain.conversation.value_objects import MessageId
from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService
from src.infrastructure.conversation.summary_recent_strategy import (
    SummaryRecentStrategy,
)

scenarios("unit/conversation/summary_cache.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _build_messages(count: int) -> list[Message]:
    messages = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(
            Message(
                id=MessageId(value=f"msg-{i}"),
                conversation_id="conv-1",
                role=role,
                content=f"Message {i}",
            )
        )
    return messages


@given("一段包含 10 則訊息的對話歷史且摘要快取 TTL 為 300 秒")
def setup_messages(context):
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            text="這是對話摘要",
            usage=TokenUsage(
                model="test", input_tokens=0, output_tokens=0, total_tokens=0
            ),
        )
    )

    cache_service = InMemoryCacheService()

    context["strategy"] = SummaryRecentStrategy(
        llm_service=mock_llm,
        cache_service=cache_service,
        cache_ttl=300,
    )
    context["messages"] = _build_messages(10)
    context["mock_llm"] = mock_llm
    context["cache_service"] = cache_service


@when("連續兩次執行 summary_recent 策略")
def execute_twice(context):
    for _ in range(2):
        _run(context["strategy"].process(context["messages"]))


@when("執行 summary_recent 策略一次")
def execute_once(context):
    _run(context["strategy"].process(context["messages"]))


@then("LLM generate 應只被呼叫一次")
def verify_single_llm_call(context):
    assert context["mock_llm"].generate.call_count == 1


@then("快取中應存在對應的摘要 key 且有 TTL")
def verify_cache_entry(context):
    cache = context["cache_service"]
    # The cache key is conv_summary:{msg_count}:{last_msg_id}
    # Old messages = 10 - 6 (default 3 turns * 2) = 4
    # Last old message id = "msg-3"
    cache_key = "conv_summary:4:msg-3"
    result = _run(cache.get(cache_key))
    assert result is not None
    assert result == "這是對話摘要"
    # Verify TTL was set (entry has non-None expires_at)
    _, expires_at = cache._store[cache_key]
    assert expires_at is not None
