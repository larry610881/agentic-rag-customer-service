"""訊息 structured_content 持久化 BDD Step Definitions"""

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

scenarios("unit/conversation/message_structured_content.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_use_case(context, *, sources=None, contact=None):
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(
            answer="測試回覆",
            tool_calls=[],
            sources=sources or [],
            contact=contact,
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


@given("一個會回傳 contact 的 Agent Service")
def setup_agent_with_contact(context):
    contact = {
        "label": "聯絡真人客服",
        "url": "https://example.com/support",
        "type": "url",
    }
    _make_use_case(context, contact=contact)


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


@given("一個只回傳純文字的 Agent Service")
def setup_agent_plain_text(context):
    _make_use_case(context)


def _make_streaming_use_case(context, *, events):
    """events: list[dict] — 模擬 agent.process_message_stream yield 的序列"""
    async def stream_generator(**_kwargs):
        for ev in events:
            yield ev

    mock_agent = AsyncMock()
    mock_agent.process_message_stream = stream_generator
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=None)
    mock_repo.save = AsyncMock()

    context["mock_agent"] = mock_agent
    context["mock_repo"] = mock_repo
    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_repo,
    )


@given("一個會在 streaming 中 yield contact event 的 Agent Service")
def setup_streaming_agent_with_contact(context):
    _make_streaming_use_case(
        context,
        events=[
            {"type": "token", "content": "為您轉接真人客服"},
            {"type": "contact", "contact": {
                "label": "聯絡真人客服",
                "url": "https://example.com/support",
                "type": "url",
            }},
            {"type": "done"},
        ],
    )


@given("一個會在 streaming 中 yield sources event 的 Agent Service")
def setup_streaming_agent_with_sources(context):
    _make_streaming_use_case(
        context,
        events=[
            {"type": "token", "content": "退貨政策內容"},
            {"type": "sources", "sources": [
                {"document_name": "退貨政策.md",
                 "content_snippet": "30 天內可退貨",
                 "score": 0.95},
            ]},
            {"type": "done"},
        ],
    )


@when(parsers.parse('使用者以 streaming 模式發送訊息 "{msg}"'))
def send_message_streaming(context, msg):
    async def collect():
        async for _ev in context["use_case"].execute_stream(
            SendMessageCommand(
                tenant_id="tenant-001",
                kb_id="kb-001",
                message=msg,
            )
        ):
            pass

    _run(collect())

    save_call = context["mock_repo"].save.call_args
    conversation = save_call[0][0]
    assistant_msgs = [m for m in conversation.messages if m.role == "assistant"]
    context["assistant_message"] = assistant_msgs[-1] if assistant_msgs else None


@then("streaming 助理訊息的 structured_content 應包含 contact 欄位")
def verify_streaming_contact(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.structured_content is not None
    contact = msg.structured_content.get("contact")
    assert contact is not None
    assert contact["label"] == "聯絡真人客服"
    assert contact["url"] == "https://example.com/support"


@then("streaming 助理訊息的 structured_content 應包含 sources 列表")
def verify_streaming_sources(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.structured_content is not None
    sources = msg.structured_content.get("sources")
    assert isinstance(sources, list)
    assert len(sources) >= 1
    assert sources[0]["document_name"] == "退貨政策.md"


@when(parsers.parse('使用者發送訊息 "{msg}"'))
def send_message(context, msg):
    _run(
        context["use_case"].execute(
            SendMessageCommand(
                tenant_id="tenant-001",
                kb_id="kb-001",
                message=msg,
            )
        )
    )

    save_call = context["mock_repo"].save.call_args
    conversation = save_call[0][0]
    assistant_msgs = [m for m in conversation.messages if m.role == "assistant"]
    context["assistant_message"] = assistant_msgs[-1] if assistant_msgs else None


@then("助理訊息的 structured_content 應包含 contact 欄位")
def verify_structured_content_contact(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.structured_content is not None
    assert "contact" in msg.structured_content
    contact = msg.structured_content["contact"]
    assert contact is not None
    assert contact["label"] == "聯絡真人客服"
    assert contact["url"] == "https://example.com/support"


@then("助理訊息的 structured_content 應包含 sources 列表")
def verify_structured_content_sources(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.structured_content is not None
    sources = msg.structured_content.get("sources")
    assert isinstance(sources, list)
    assert len(sources) >= 1
    assert sources[0]["document_name"] == "退貨政策.md"


@then("助理訊息的 structured_content 應為 None")
def verify_structured_content_none(context):
    msg = context["assistant_message"]
    assert msg is not None
    assert msg.structured_content is None
