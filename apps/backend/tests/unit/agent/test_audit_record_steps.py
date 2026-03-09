"""BDD steps for Audit Record mode."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.infrastructure.langgraph.react_agent_service import ReActAgentService
from src.infrastructure.langgraph.tools import RAGQueryTool

scenarios("unit/agent/audit_record.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture()
def context():
    return {}


def _build_service():
    llm_service = AsyncMock()
    rag_tool = AsyncMock(spec=RAGQueryTool)
    return ReActAgentService(llm_service=llm_service, rag_tool=rag_tool)


def _make_rag_tool(return_value: str):
    @tool
    async def rag_query(query: str) -> str:
        """查詢知識庫回答用戶問題。

        Args:
            query: 要查詢的問題
        """
        return return_value

    return rag_query


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(parsers.parse('一個 audit_mode 為 "{mode}" 的設定'))
def setup_audit_mode(context, mode):
    context["service"] = _build_service()
    context["audit_mode"] = mode


@given("一個未設定 audit_mode 的 Bot")
def setup_default_bot(context):
    context["bot"] = Bot()


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("ReAct Agent 處理一次工具呼叫")
def react_agent_processes(context):
    service = context["service"]
    audit_mode = context["audit_mode"]

    rag_lc_tool = _make_rag_tool("退貨政策：7天內可退貨")

    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "rag_query",
                        "args": {"query": "退貨政策"},
                        "id": "call_1",
                    },
                ],
            ),
            AIMessage(content="根據退貨政策，您可以在7天內退貨。"),
        ]
    )

    with (
        patch.object(
            service,
            "_resolve_llm_model",
            new=AsyncMock(return_value=mock_llm),
        ),
        patch.object(service, "_build_rag_lc_tool", return_value=rag_lc_tool),
        patch.object(
            service, "_load_mcp_tools_with_stack",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = _run(
            service.process_message(
                tenant_id="tenant-1",
                kb_id="kb-1",
                user_message="退貨政策是什麼？",
                audit_mode=audit_mode,
            )
        )

    context["result"] = result


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("tool_calls 應包含 tool_name")
def check_has_tool_name(context):
    result: AgentResponse = context["result"]
    assert len(result.tool_calls) > 0
    assert "tool_name" in result.tool_calls[0]
    assert result.tool_calls[0]["tool_name"] == "rag_query"


@then("tool_calls 不應包含 tool_input")
def check_no_tool_input(context):
    result: AgentResponse = context["result"]
    for tc in result.tool_calls:
        assert "tool_input" not in tc


@then("tool_calls 應包含 tool_input")
def check_has_tool_input(context):
    result: AgentResponse = context["result"]
    found = any("tool_input" in tc for tc in result.tool_calls)
    assert found, f"Expected tool_input in tool_calls: {result.tool_calls}"


@then("tool_calls 應包含 iteration")
def check_has_iteration(context):
    result: AgentResponse = context["result"]
    found = any("iteration" in tc for tc in result.tool_calls)
    assert found, f"Expected iteration in tool_calls: {result.tool_calls}"


@then(parsers.parse('Bot 的 audit_mode 應為 "{expected}"'))
def check_bot_default_audit_mode(context, expected):
    bot: Bot = context["bot"]
    assert bot.audit_mode == expected
