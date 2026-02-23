"""對話記憶 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.agent.entity import AgentResponse
from src.domain.conversation.entity import Conversation
from src.domain.conversation.value_objects import ConversationId
from src.domain.rag.value_objects import TokenUsage

scenarios("unit/conversation/conversation_memory.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_use_case(context, conversation=None):
    has_history = conversation and conversation.messages
    answer = (
        "根據先前對話，退貨政策為 30 天內可退貨。"
        if has_history
        else "根據知識庫：退貨政策為 30 天內可退貨。"
    )
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(
            answer=answer,
            tool_calls=[
                {"tool_name": "rag_query", "reasoning": "知識型問題"}
            ],
            conversation_id="temp",
            usage=TokenUsage.zero("fake"),
        )
    )
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=conversation)
    mock_repo.save = AsyncMock()

    context["mock_agent"] = mock_agent
    context["mock_repo"] = mock_repo
    context["use_case"] = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=mock_repo,
    )


@given(parsers.parse('租戶 "{tenant_id}" 已有一個對話'))
def tenant_has_conversation(context, tenant_id):
    conv = Conversation(
        id=ConversationId(value="conv-001"),
        tenant_id=tenant_id,
    )
    context["conversation"] = conv
    context["tenant_id"] = tenant_id


@given(parsers.parse('對話中已有使用者訊息 "{msg}"'))
def conversation_has_message(context, msg):
    context["conversation"].add_message("user", msg)
    context["conversation"].add_message("assistant", "您好，很高興為您服務")
    _make_use_case(context, context["conversation"])


@when(parsers.parse('使用者在同一對話發送 "{msg}"'))
def send_message_in_same_conversation(context, msg):
    context["response"] = _run(
        context["use_case"].execute(
            SendMessageCommand(
                tenant_id=context["tenant_id"],
                kb_id="kb-001",
                message=msg,
                conversation_id="conv-001",
            )
        )
    )


@then(parsers.parse('Agent 回應應包含 "{text}"'))
def response_should_contain(context, text):
    assert text in context["response"].answer


@given(parsers.parse('租戶 "{tenant_id}" 發送第一條訊息 "{msg}"'))
def send_first_message(context, tenant_id, msg):
    context["tenant_id"] = tenant_id
    _make_use_case(context, None)
    context["response1"] = _run(
        context["use_case"].execute(
            SendMessageCommand(
                tenant_id=tenant_id,
                kb_id="kb-001",
                message=msg,
            )
        )
    )
    context["conv_id"] = context["response1"].conversation_id

    conv = Conversation(
        id=ConversationId(value=context["conv_id"]),
        tenant_id=tenant_id,
    )
    conv.add_message("user", msg)
    conv.add_message("assistant", context["response1"].answer)
    _make_use_case(context, conv)


@when(parsers.parse('使用者用相同 conversation_id 發送第二條訊息 "{msg}"'))
def send_second_message_same_conv(context, msg):
    context["response2"] = _run(
        context["use_case"].execute(
            SendMessageCommand(
                tenant_id=context["tenant_id"],
                kb_id="kb-001",
                message=msg,
                conversation_id=context["conv_id"],
            )
        )
    )


@then("兩次回應的 conversation_id 應一致")
def verify_conversation_id_consistent(context):
    assert context["response1"].conversation_id == context["response2"].conversation_id


@given(parsers.parse('租戶 "{tenant_id}" 未建立對話'))
def tenant_no_conversation(context, tenant_id):
    context["tenant_id"] = tenant_id
    _make_use_case(context, None)


@when(parsers.parse('使用者發送新對話訊息 "{msg}"'))
def send_new_conversation_message(context, msg):
    context["response"] = _run(
        context["use_case"].execute(
            SendMessageCommand(
                tenant_id=context["tenant_id"],
                kb_id="kb-001",
                message=msg,
            )
        )
    )


@then(parsers.parse('Agent 回應不應包含 "{text}"'))
def response_should_not_contain(context, text):
    assert text not in context["response"].answer
