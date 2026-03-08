"""BDD steps for MCP 工具快取."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.mcp.cached_tool_loader import CachedMCPToolLoader

scenarios("unit/agent/mcp_cache.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def _make_mock_tool(name: str) -> MagicMock:
    """Create a mock BaseTool with a given name."""
    mock = MagicMock()
    mock.name = name
    return mock


@pytest.fixture()
def context():
    return {}


# ---------------------------------------------------------------------------
# Scenario: 首次載入觸發連線
# ---------------------------------------------------------------------------


@given("一個空的 MCP 快取載入器")
def setup_empty_loader(context):
    context["loader"] = CachedMCPToolLoader(ttl=300)
    context["mock_tools"] = [_make_mock_tool("rag_query")]
    context["connect_count"] = 0


@when(parsers.parse('載入 MCP 工具從 "{url}"'))
def load_mcp_tools(context, url):
    loader = context["loader"]
    mock_tools = context["mock_tools"]

    original_count = context.get("connect_count", 0)

    async def fake_connect(server_url):
        context["connect_count"] = context.get("connect_count", 0) + 1
        return list(mock_tools)

    async def _do():
        with patch.object(
            CachedMCPToolLoader,
            "_connect_and_load",
            side_effect=fake_connect,
        ):
            return await loader.load_tools(url)

    context["result"] = _run(_do())


@then("應建立一次 SSE 連線")
def check_one_connection(context):
    assert context["connect_count"] == 1


@then("應回傳工具列表")
def check_returns_tools(context):
    assert len(context["result"]) >= 1


# ---------------------------------------------------------------------------
# Scenario: 快取命中不重新連線
# ---------------------------------------------------------------------------


@given(parsers.parse('一個已快取 "{url}" 工具的載入器'))
def setup_cached_loader(context, url):
    loader = CachedMCPToolLoader(ttl=300)
    mock_tools = [_make_mock_tool("rag_query")]
    context["loader"] = loader
    context["mock_tools"] = mock_tools
    context["connect_count"] = 0

    async def fake_connect(server_url):
        context["connect_count"] = context.get("connect_count", 0) + 1
        return list(mock_tools)

    # Pre-fill cache
    async def _warmup():
        with patch.object(
            CachedMCPToolLoader,
            "_connect_and_load",
            side_effect=fake_connect,
        ):
            await loader.load_tools(url)

    _run(_warmup())
    # Reset counter after warmup
    context["connect_count"] = 0


@when(parsers.parse('再次載入 MCP 工具從 "{url}"'))
def reload_mcp_tools(context, url):
    loader = context["loader"]

    async def fake_connect(server_url):
        context["connect_count"] = context.get("connect_count", 0) + 1
        return list(context["mock_tools"])

    async def _do():
        with patch.object(
            CachedMCPToolLoader,
            "_connect_and_load",
            side_effect=fake_connect,
        ):
            return await loader.load_tools(url)

    context["result"] = _run(_do())


@then("不應建立新的 SSE 連線")
def check_no_new_connection(context):
    assert context["connect_count"] == 0


@then("應回傳相同的工具列表")
def check_same_tools(context):
    assert len(context["result"]) >= 1


# ---------------------------------------------------------------------------
# Scenario: 快取過期後重新載入
# ---------------------------------------------------------------------------


@given("一個已快取但 TTL 已過期的載入器")
def setup_expired_loader(context):
    loader = CachedMCPToolLoader(ttl=1)  # 1 second TTL
    mock_tools = [_make_mock_tool("rag_query")]
    context["loader"] = loader
    context["mock_tools"] = mock_tools
    context["connect_count"] = 0

    async def fake_connect(server_url):
        context["connect_count"] = context.get("connect_count", 0) + 1
        return list(mock_tools)

    # Pre-fill cache
    async def _warmup():
        with patch.object(
            CachedMCPToolLoader,
            "_connect_and_load",
            side_effect=fake_connect,
        ):
            await loader.load_tools("http://mcp.example.com")

    _run(_warmup())
    # Reset and wait for expiry
    context["connect_count"] = 0
    # Manually expire the cache by adjusting the timestamp
    for key in loader._cache:
        tools, _ = loader._cache[key]
        loader._cache[key] = (tools, time.monotonic() - 10)


@then("應建立新的 SSE 連線")
def check_new_connection(context):
    assert context["connect_count"] >= 1


# ---------------------------------------------------------------------------
# Scenario: 篩選特定工具
# ---------------------------------------------------------------------------


@given(parsers.parse('一個已快取包含 "{tool_a}" 和 "{tool_b}" 的載入器'))
def setup_multi_tool_loader(context, tool_a, tool_b):
    loader = CachedMCPToolLoader(ttl=300)
    mock_tools = [_make_mock_tool(tool_a), _make_mock_tool(tool_b)]
    context["loader"] = loader
    context["mock_tools"] = mock_tools

    async def fake_connect(server_url):
        return list(mock_tools)

    # Pre-fill cache
    async def _warmup():
        with patch.object(
            CachedMCPToolLoader,
            "_connect_and_load",
            side_effect=fake_connect,
        ):
            await loader.load_tools("http://mcp.example.com")

    _run(_warmup())


@when(parsers.parse('以 ["{tool_name}"] 篩選載入'))
def load_with_filter(context, tool_name):
    loader = context["loader"]

    async def _do():
        return await loader.load_tools(
            "http://mcp.example.com",
            enabled_tools=[tool_name],
        )

    context["result"] = _run(_do())


@then(parsers.parse("應只回傳 {n:d} 個工具"))
def check_filtered_count(context, n):
    assert len(context["result"]) == n
