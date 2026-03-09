"""BDD steps for ReAct Agent Execution."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.agent.entity import AgentResponse
from src.infrastructure.langgraph.react_agent_service import ReActAgentService
from src.infrastructure.langgraph.tools import RAGQueryTool

scenarios("unit/agent/react_agent_execution.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture()
def context():
    return {}


def _make_mock_llm(side_effects: list[AIMessage]):
    """Create a mock LLM that returns different AIMessages on consecutive calls.

    Uses MagicMock (not AsyncMock) so bind_tools() is synchronous,
    matching the real ChatModel API. Only ainvoke is async.
    """
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(side_effect=side_effects)
    return mock_llm


def _make_rag_tool(return_value: str):
    """Create a real @tool function that returns a fixed value."""

    @tool
    async def rag_query(query: str) -> str:
        """查詢知識庫回答用戶問題，適用於退貨政策、使用說明等知識型問題。

        Args:
            query: 要查詢的問題
        """
        return return_value

    return rag_query


def _make_mcp_tool(tool_name: str, return_value: str):
    """Create a real @tool function that simulates an MCP tool."""

    @tool
    async def mcp_tool_fn(query: str = "") -> str:
        """查詢外部系統的 MCP 工具。

        Args:
            query: 查詢內容
        """
        return return_value

    mcp_tool_fn.name = tool_name
    return mcp_tool_fn


def _build_service():
    """Build a ReActAgentService with mocked dependencies."""
    llm_service = AsyncMock()
    rag_tool = AsyncMock(spec=RAGQueryTool)
    return ReActAgentService(llm_service=llm_service, rag_tool=rag_tool)


def _patch_and_run(service, mock_llm, rag_lc_tool, mcp_tools, **process_kwargs):
    """Patch service internals and run process_message."""
    with (
        patch.object(
            service, "_resolve_llm_model", new=AsyncMock(return_value=mock_llm)
        ),
        patch.object(service, "_build_rag_lc_tool", return_value=rag_lc_tool),
        patch.object(
            service, "_load_mcp_tools_with_stack",
            new=AsyncMock(return_value=mcp_tools),
        ),
    ):
        return _run(service.process_message(**process_kwargs))


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("一個 ReAct Agent 配置了 RAG 工具")
def setup_react_agent_with_rag(context):
    context["service"] = _build_service()
    context["rag_return"] = ""
    context["max_tool_calls"] = 5
    context["mcp_return"] = {}


@given(parsers.parse('RAG 工具查詢後回傳 "{text}"'))
def setup_rag_return(context, text):
    context["rag_return"] = text


@given(parsers.parse('一個 ReAct Agent 配置了 MCP 工具 "{tool_name}"'))
def setup_react_agent_with_mcp(context, tool_name):
    context["service"] = _build_service()
    context["rag_return"] = ""
    context["max_tool_calls"] = 5
    context["mcp_tool_name"] = tool_name
    context["mcp_return"] = {}


@given(parsers.parse('MCP 工具 "{tool_name}" 回傳 "{text}"'))
def setup_mcp_return(context, tool_name, text):
    context["mcp_tool_name"] = tool_name
    context["mcp_return"] = {tool_name: text}


@given("一個 ReAct Agent 配置了 RAG 和 MCP 工具")
def setup_react_agent_with_rag_and_mcp(context):
    context["service"] = _build_service()
    context["rag_return"] = ""
    context["max_tool_calls"] = 5
    context["mcp_return"] = {}
    context["has_both"] = True


@given(parsers.parse("max_tool_calls 設為 {n:d}"))
def setup_max_tool_calls(context, n):
    context["max_tool_calls"] = n


@given("一個 ReAct Agent 配置了 MCP 工具但連線失敗")
def setup_react_agent_mcp_failure(context):
    context["service"] = _build_service()
    context["rag_return"] = ""
    context["max_tool_calls"] = 5
    context["mcp_failure"] = True


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(parsers.parse('用戶詢問 "{question}"'))
def user_asks(context, question):
    service = context["service"]
    rag_return = context.get("rag_return", "")
    max_tool_calls = context.get("max_tool_calls", 5)

    rag_lc_tool = _make_rag_tool(rag_return)

    # Build MCP tools if configured
    mcp_tools = []
    mcp_return = context.get("mcp_return", {})
    for name, ret in mcp_return.items():
        mcp_tools.append(_make_mcp_tool(name, ret))

    if context.get("has_both"):
        llm_responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "rag_query", "args": {"query": question}, "id": "call_1"},
                ],
            ),
            AIMessage(content=f"根據查詢結果：{rag_return}"),
        ]
    elif mcp_return and not rag_return:
        mcp_name = list(mcp_return.keys())[0]
        mcp_text = list(mcp_return.values())[0]
        llm_responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": mcp_name, "args": {"query": question}, "id": "call_1"},
                ],
            ),
            AIMessage(content=f"根據查詢結果：{mcp_text}"),
        ]
    else:
        llm_responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "rag_query", "args": {"query": question}, "id": "call_1"},
                ],
            ),
            AIMessage(content=f"根據查詢結果：{rag_return}"),
        ]

    mock_llm = _make_mock_llm(llm_responses)

    result = _patch_and_run(
        service,
        mock_llm,
        rag_lc_tool,
        mcp_tools if not context.get("mcp_failure") else [],
        tenant_id="tenant-1",
        kb_id="kb-1",
        user_message=question,
        mcp_servers=(
            [{"url": "http://fake-mcp", "enabled_tools": None}]
            if (mcp_return or context.get("mcp_failure"))
            else None
        ),
        max_tool_calls=max_tool_calls,
    )
    context["result"] = result
    context["mock_llm"] = mock_llm


@when("用戶詢問需要多次查詢的問題")
def user_asks_multi_query(context):
    service = context["service"]
    rag_return = context.get("rag_return", "知識庫資訊")
    max_tool_calls = context.get("max_tool_calls", 5)

    rag_lc_tool = _make_rag_tool(rag_return)

    # LLM wants to call tools 3 times, but max_tool_calls=2 should stop it
    llm_responses = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "rag_query", "args": {"query": "第一次查詢"}, "id": "call_1"},
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "rag_query", "args": {"query": "第二次查詢"}, "id": "call_2"},
            ],
        ),
        AIMessage(content="最終回答"),
    ]

    mock_llm = _make_mock_llm(llm_responses)

    result = _patch_and_run(
        service,
        mock_llm,
        rag_lc_tool,
        [],
        tenant_id="tenant-1",
        kb_id="kb-1",
        user_message="需要多次查詢的問題",
        max_tool_calls=max_tool_calls,
    )
    context["result"] = result
    context["mock_llm"] = mock_llm


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("Agent 應呼叫 rag_query 工具")
def check_rag_tool_called(context):
    result: AgentResponse = context["result"]
    tool_names = [tc["tool_name"] for tc in result.tool_calls]
    assert "rag_query" in tool_names


@then("Agent 應呼叫 query_products 工具")
def check_mcp_tool_called(context):
    result: AgentResponse = context["result"]
    tool_names = [tc["tool_name"] for tc in result.tool_calls]
    assert "query_products" in tool_names


@then("最終回答應包含工具結果")
def check_answer_contains_result(context):
    result: AgentResponse = context["result"]
    assert result.answer != ""


@then(parsers.parse("Agent 應呼叫至少 {n:d} 個工具"))
def check_min_tool_calls(context, n):
    result: AgentResponse = context["result"]
    real_calls = [tc for tc in result.tool_calls if tc["tool_name"] != "direct"]
    assert len(real_calls) >= n


@then(parsers.parse("Agent 的工具呼叫次數不應超過 {n:d} 次"))
def check_max_tool_calls(context, n):
    result: AgentResponse = context["result"]
    real_calls = [tc for tc in result.tool_calls if tc["tool_name"] != "direct"]
    assert len(real_calls) <= n


@then("Agent 應正常運作只使用 RAG 工具")
def check_only_rag_used(context):
    result: AgentResponse = context["result"]
    tool_names = [tc["tool_name"] for tc in result.tool_calls]
    assert "rag_query" in tool_names
    for name in tool_names:
        assert name in ("rag_query", "direct")
