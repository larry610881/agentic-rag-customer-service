"""訊息 Metadata（latency_ms + retrieved_chunks）BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.rag.value_objects import Source, TokenUsage

scenarios("unit/conversation/message_metadata.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_use_case(context, *, sources=None):
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(
            answer="退貨政策為 30 天內可退貨。",
            tool_calls=[],
            sources=sources or [],
            conversation_id="temp",
            usage=TokenUsage.zero("fake"),
        )
    )
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=None)
    mock_repo.save = AsyncMock()

    context["mock_agent"] = mock_agent
    context["mock_repo"] = mock_repo
    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_repo,
    )


@given("一個已設定好的 Agent Service")
def setup_agent_service(context):
    _make_use_case(context)


@given("一個回傳來源引用的 Agent Service")
def setup_agent_with_sources(context):
    sources = [
        Source(
            document_name="退貨政策.md",
            content_snippet="30 天內可退貨",
            score=0.95,
            chunk_id="chunk-001",
        ),
    ]
    _make_use_case(context, sources=sources)


@given("一個不回傳來源的 Agent Service")
def setup_agent_without_sources(context):
    _make_use_case(context, sources=[])


@when(parsers.parse('使用者發送訊息 "{msg}"'))
def send_message(context, msg):
    response = _run(
        context["use_case"].execute(
            SendMessageCommand(
                tenant_id="tenant-001",
                kb_id="kb-001",
                message=msg,
            )
        )
    )
    context["response"] = response

    # Get the saved conversation to inspect message metadata
    save_call = context["mock_repo"].save.call_args
    conversation = save_call[0][0]
    # Find the assistant message (last one)
    assistant_msgs = [m for m in conversation.messages if m.role == "assistant"]
    context["assistant_message"] = assistant_msgs[-1] if assistant_msgs else None


@then("助理訊息應包含 latency_ms 且為正整數")
def verify_latency_ms(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.latency_ms is not None
    assert isinstance(msg.latency_ms, int)
    assert msg.latency_ms >= 0


@then("助理訊息應包含 retrieved_chunks 列表")
def verify_retrieved_chunks(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.retrieved_chunks is not None
    assert isinstance(msg.retrieved_chunks, list)
    assert len(msg.retrieved_chunks) >= 1
    assert "document_name" in msg.retrieved_chunks[0]
    assert "score" in msg.retrieved_chunks[0]


@then("助理訊息的 retrieved_chunks 應為 None")
def verify_no_retrieved_chunks(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.retrieved_chunks is None
