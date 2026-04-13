"""BDD steps for MCP 工具載入器（stack-based, no cache）."""
import asyncio
from contextlib import AsyncExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.mcp.cached_tool_loader import CachedMCPToolLoader

scenarios("unit/agent/mcp_cache.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_tool(name: str) -> MagicMock:
    """Create a mock BaseTool with a given name."""
    mock = MagicMock()
    mock.name = name
    return mock


@pytest.fixture()
def context():
    return {}


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("一個 MCP 工具載入器")
def setup_loader(context):
    context["loader"] = CachedMCPToolLoader()
    context["mock_tools"] = [_make_mock_tool("rag_query")]
    context["connect_count"] = 0


@given(parsers.parse('MCP Server 提供 "{tool_a}" 和 "{tool_b}" 兩個工具'))
def setup_multi_tools(context, tool_a, tool_b):
    context["mock_tools"] = [_make_mock_tool(tool_a), _make_mock_tool(tool_b)]


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(parsers.parse('透過 stack 載入 MCP 工具從 "{url}"'))
def load_mcp_tools_via_stack(context, url):
    loader = context["loader"]
    mock_tools = context["mock_tools"]

    async def fake_connect(stack, server_url, enabled_tools=None):
        context["connect_count"] = context.get("connect_count", 0) + 1
        if enabled_tools:
            return [t for t in mock_tools if t.name in enabled_tools]
        return list(mock_tools)

    async def _do():
        async with AsyncExitStack() as stack:
            with patch.object(
                CachedMCPToolLoader,
                "_connect_and_load",
                side_effect=fake_connect,
            ):
                return await loader.load_tools(stack, url)

    context["result"] = _run(_do())


@when(parsers.parse('以 ["{tool_name}"] 篩選載入'))
def load_with_filter(context, tool_name):
    loader = context["loader"]
    mock_tools = context["mock_tools"]

    async def fake_connect(stack, server_url, enabled_tools=None):
        context["connect_count"] = context.get("connect_count", 0) + 1
        if enabled_tools:
            return [t for t in mock_tools if t.name in enabled_tools]
        return list(mock_tools)

    async def _do():
        async with AsyncExitStack() as stack:
            with patch.object(
                CachedMCPToolLoader,
                "_connect_and_load",
                side_effect=fake_connect,
            ):
                return await loader.load_tools(
                    stack, "http://mcp.example.com",
                    enabled_tools=[tool_name],
                )

    context["result"] = _run(_do())


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("應建立一次連線")
def check_one_connection(context):
    assert context["connect_count"] == 1


@then("應回傳工具列表")
def check_returns_tools(context):
    assert len(context["result"]) >= 1


@then(parsers.parse("應只回傳 {n:d} 個工具"))
def check_filtered_count(context, n):
    assert len(context["result"]) == n
