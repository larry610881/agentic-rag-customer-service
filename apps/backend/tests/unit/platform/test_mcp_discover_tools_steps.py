"""MCP Server Tool Discovery BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.platform.mcp.discover_mcp_server_use_case import (
    DiscoverMcpServerUseCase,
)
from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.value_objects import McpRegistryId, McpRegistryToolMeta

scenarios("unit/platform/mcp_discover_tools.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_mcp_repo():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    return repo


async def _fake_do_discover(**kwargs):
    """Match the signature of _do_discover (keyword-only args)."""
    return [
        McpRegistryToolMeta(name="query_products", description="查詢商品"),
        McpRegistryToolMeta(name="query_courses", description="查詢課程"),
    ]


@given("一個可連線的 HTTP MCP Server")
def http_mcp_server(context):
    context["transport"] = "http"
    context["url"] = "http://localhost:3000/mcp"


@given("一個可連線的 HTTP MCP Server 且已在註冊庫中")
def http_mcp_server_registered(context, mock_mcp_repo):
    context["transport"] = "http"
    context["url"] = "http://localhost:3000/mcp"
    context["server_id"] = "reg-1"
    server = McpServerRegistration(
        id=McpRegistryId(value="reg-1"),
        name="test-server",
        url="http://localhost:3000/mcp",
    )
    mock_mcp_repo.find_by_id.return_value = server


@given("一個可連線的 stdio MCP Server")
def stdio_mcp_server(context):
    context["transport"] = "stdio"
    context["command"] = "python"
    context["args"] = ["-m", "server"]


@when("我執行工具探索")
def discover_http(context, mock_mcp_repo):
    use_case = DiscoverMcpServerUseCase(mcp_server_repository=mock_mcp_repo)

    with patch.object(
        DiscoverMcpServerUseCase,
        "_do_discover",
        side_effect=_fake_do_discover,
    ):
        context["tools"] = _run(
            use_case.execute(
                transport=context["transport"],
                url=context.get("url", ""),
            )
        )


@when("我執行工具探索並指定 server_id")
def discover_with_server_id(context, mock_mcp_repo):
    use_case = DiscoverMcpServerUseCase(mcp_server_repository=mock_mcp_repo)

    with patch.object(
        DiscoverMcpServerUseCase,
        "_do_discover",
        side_effect=_fake_do_discover,
    ):
        context["tools"] = _run(
            use_case.execute(
                transport=context["transport"],
                url=context.get("url", ""),
                server_id=context["server_id"],
            )
        )


@when("我執行 stdio 工具探索")
def discover_stdio(context, mock_mcp_repo):
    use_case = DiscoverMcpServerUseCase(mcp_server_repository=mock_mcp_repo)

    async def _fake_stdio(**kwargs):
        return [McpRegistryToolMeta(name="stdio_tool", description="stdio")]

    with patch.object(
        DiscoverMcpServerUseCase,
        "_do_discover",
        side_effect=_fake_stdio,
    ):
        context["tools"] = _run(
            use_case.execute(
                transport="stdio",
                command=context.get("command", ""),
                args=context.get("args", []),
            )
        )


@then("應回傳工具列表")
def tools_returned(context):
    assert len(context["tools"]) >= 1


@then("註冊庫中的 available_tools 應被更新")
def registry_updated(context, mock_mcp_repo):
    mock_mcp_repo.save.assert_called_once()


@then("應回傳 stdio 工具列表")
def stdio_tools_returned(context):
    assert len(context["tools"]) >= 1
    assert context["tools"][0].name == "stdio_tool"
