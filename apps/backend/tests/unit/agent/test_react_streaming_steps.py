"""BDD steps for ReAct Agent Streaming."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.langgraph.react_agent_service import ReActAgentService
from src.infrastructure.langgraph.tools import RAGQueryTool

scenarios("unit/agent/react_streaming.feature")


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


def _make_rag_tool(return_value: str = "知識庫結果"):
    @tool
    async def rag_query(query: str) -> str:
        """查詢知識庫回答用戶問題。

        Args:
            query: 要查詢的問題
        """
        return return_value

    return rag_query


def _make_extra_tool(tool_name: str, return_value: str = "工具結果"):
    @tool
    async def extra_tool(query: str = "") -> str:
        """查詢額外資訊的工具。

        Args:
            query: 查詢內容
        """
        return return_value

    extra_tool.name = tool_name
    return extra_tool


def _build_service():
    llm_service = AsyncMock()
    rag_tool = AsyncMock(spec=RAGQueryTool)
    return ReActAgentService(llm_service=llm_service, rag_tool=rag_tool)


# ---------------------------------------------------------------------------
# Scenario: 單次工具呼叫的事件序列
# ---------------------------------------------------------------------------


@given("一個配置了 RAG 工具的 Streaming ReAct Agent")
def setup_streaming_rag_agent(context):
    context["service"] = _build_service()
    context["extra_tools"] = []


@given("LLM 會先呼叫工具再生成回答")
def setup_single_tool_call(context):
    context["llm_responses"] = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "rag_query", "args": {"query": "測試查詢"}, "id": "call_1"},
            ],
        ),
        AIMessage(content="根據查詢結果，這是回答。"),
    ]


# ---------------------------------------------------------------------------
# Scenario: 多輪工具呼叫的事件序列
# ---------------------------------------------------------------------------


@given("一個配置了多個工具的 Streaming ReAct Agent")
def setup_streaming_multi_tool_agent(context):
    context["service"] = _build_service()
    context["extra_tools"] = [_make_extra_tool("lookup_tool")]


@given("LLM 會呼叫兩次工具後再生成回答")
def setup_double_tool_call(context):
    context["llm_responses"] = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "rag_query", "args": {"query": "第一次查詢"}, "id": "call_1"},
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "lookup_tool", "args": {"query": "第二次查詢"}, "id": "call_2"},
            ],
        ),
        AIMessage(content="綜合兩次查詢結果，這是最終回答。"),
    ]


# ---------------------------------------------------------------------------
# When step
# ---------------------------------------------------------------------------


@when("以 streaming 模式處理用戶訊息")
def stream_message(context):
    service = context["service"]
    rag_lc_tool = _make_rag_tool()
    extra_tools = context.get("extra_tools", [])
    mock_llm = _make_mock_llm(context["llm_responses"])

    async def _collect_events():
        with (
            patch.object(
                service, "_resolve_llm_model",
                new=AsyncMock(return_value=mock_llm),
            ),
            patch.object(service, "_build_rag_lc_tool", return_value=rag_lc_tool),
            patch.object(
                service, "_load_mcp_tools",
                new=AsyncMock(return_value=extra_tools),
            ),
        ):
            events = []
            async for event in service.process_message_stream(
                tenant_id="tenant-1",
                kb_id="kb-1",
                user_message="測試訊息",
            ):
                events.append(event)
            return events

    context["events"] = _run(_collect_events())


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("事件序列應包含 tool_calls 事件")
def check_has_tool_calls_event(context):
    events = context["events"]
    tool_call_events = [e for e in events if e["type"] == "tool_calls"]
    assert len(tool_call_events) >= 1


@then("事件序列應包含 token 事件")
def check_has_token_event(context):
    events = context["events"]
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) >= 1


@then("最後一個事件應為 done")
def check_last_event_done(context):
    events = context["events"]
    assert events[-1]["type"] == "done"


@then(parsers.parse("事件序列應包含至少 {n:d} 個 tool_calls 事件"))
def check_min_tool_calls_events(context, n):
    events = context["events"]
    tool_call_events = [e for e in events if e["type"] == "tool_calls"]
    assert len(tool_call_events) >= n
