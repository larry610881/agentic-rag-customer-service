"""MCP Tool Loader stdio Transport BDD Step Definitions"""

import asyncio
from contextlib import AsyncExitStack
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.mcp.cached_tool_loader import CachedMCPToolLoader

scenarios("unit/agent/tool_loader_stdio.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_mock_tool(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


@given("一個 stdio 類型的 MCP Server 配置")
def stdio_config(context):
    context["server_config"] = {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "server"],
        "env": {"DB_URL": "mysql://localhost/db"},
    }


@given(parsers.parse('一個 legacy URL 字串 "{url}"'))
def legacy_url(context, url):
    context["server_config"] = url


@when("我透過 CachedMCPToolLoader 載入工具")
def load_tools(context):
    loader = CachedMCPToolLoader()
    mock_tools = [_make_mock_tool("tool1"), _make_mock_tool("tool2")]

    async def _fake_connect_and_load(stack, server_config, enabled_tools=None):
        return mock_tools

    with patch.object(
        CachedMCPToolLoader,
        "_connect_and_load",
        side_effect=_fake_connect_and_load,
    ):

        async def _do():
            async with AsyncExitStack() as stack:
                return await loader.load_tools(
                    stack, context["server_config"]
                )

        context["tools"] = _run(_do())


@then("應成功載入 stdio 工具")
def stdio_tools_loaded(context):
    assert len(context["tools"]) >= 1


@then("應以 HTTP transport 載入工具")
def http_tools_loaded(context):
    assert len(context["tools"]) >= 1
