"""MCP Registry Binding Resolution BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.domain.bot.entity import Bot, BotMcpBinding
from src.domain.bot.value_objects import BotId
from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.value_objects import McpRegistryId

scenarios("unit/agent/mcp_registry_binding.feature")


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
def mock_bot_repo():
    return AsyncMock()


@pytest.fixture
def mock_mcp_registry_repo():
    return AsyncMock()


@pytest.fixture
def mock_conversation_repo():
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


def _make_bot(mcp_bindings=None, tenant_id="t-1"):
    return Bot(
        id=BotId(value="bot-1"),
        tenant_id=tenant_id,
        name="test-bot",
        agent_mode="react",
        mcp_bindings=mcp_bindings or [],
    )


@given("一個 Bot 綁定了 HTTP Registry Server")
def bot_with_http_binding(context, mock_bot_repo):
    bot = _make_bot(
        mcp_bindings=[
            BotMcpBinding(
                registry_id="reg-http-1",
                enabled_tools=["query_products"],
                env_values={"API_KEY": "sk-123"},
            )
        ]
    )
    mock_bot_repo.find_by_id.return_value = bot
    context["bot"] = bot


@given("Registry 中有對應的 enabled MCP Server")
def registry_has_http_server(context, mock_mcp_registry_repo):
    server = McpServerRegistration(
        id=McpRegistryId(value="reg-http-1"),
        name="product-api",
        transport="http",
        url="http://localhost:3000/mcp",
        is_enabled=True,
    )
    mock_mcp_registry_repo.find_by_id.return_value = server


@given("一個 Bot 綁定了 stdio Registry Server")
def bot_with_stdio_binding(context, mock_bot_repo):
    bot = _make_bot(
        mcp_bindings=[
            BotMcpBinding(
                registry_id="reg-stdio-1",
                enabled_tools=[],
                env_values={"DB_URL": "mysql://localhost/db"},
            )
        ]
    )
    mock_bot_repo.find_by_id.return_value = bot
    context["bot"] = bot


@given("Registry 中有對應的 stdio MCP Server")
def registry_has_stdio_server(context, mock_mcp_registry_repo):
    server = McpServerRegistration(
        id=McpRegistryId(value="reg-stdio-1"),
        name="local-tool",
        transport="stdio",
        command="python",
        args=["-m", "server"],
        is_enabled=True,
    )
    mock_mcp_registry_repo.find_by_id.return_value = server


@given("一個 Bot 綁定了已停用的 Registry Server")
def bot_with_disabled_binding(context, mock_bot_repo, mock_mcp_registry_repo):
    bot = _make_bot(
        mcp_bindings=[
            BotMcpBinding(registry_id="reg-disabled-1")
        ]
    )
    mock_bot_repo.find_by_id.return_value = bot
    context["bot"] = bot
    server = McpServerRegistration(
        id=McpRegistryId(value="reg-disabled-1"),
        name="disabled-server",
        transport="http",
        url="http://disabled:3000/mcp",
        is_enabled=False,
    )
    mock_mcp_registry_repo.find_by_id.return_value = server


@when("載入 Bot 配置")
def load_bot_config(
    context, mock_bot_repo, mock_conversation_repo, mock_mcp_registry_repo
):
    use_case = SendMessageUseCase(
        agent_service=AsyncMock(),
        conversation_repository=mock_conversation_repo,
        bot_repository=mock_bot_repo,
        mcp_registry_repo=mock_mcp_registry_repo,
    )
    command = SendMessageCommand(
        tenant_id="t-1", bot_id="bot-1", message="hi",
    )
    cfg = _run(use_case._load_bot_config(command))
    context["cfg"] = cfg


@then("mcp_servers 應包含 Registry 解析的 HTTP server")
def cfg_has_http_server(context):
    servers = context["cfg"]["mcp_servers"]
    assert len(servers) >= 1
    s = servers[0]
    assert s["name"] == "product-api"
    assert s["transport"] == "http"
    assert s["url"] == "http://localhost:3000/mcp"
    assert s["enabled_tools"] == ["query_products"]


@then("mcp_servers 應包含 Registry 解析的 stdio server")
def cfg_has_stdio_server(context):
    servers = context["cfg"]["mcp_servers"]
    assert len(servers) >= 1
    s = servers[0]
    assert s["name"] == "local-tool"
    assert s["transport"] == "stdio"
    assert s["command"] == "python"
    assert s["args"] == ["-m", "server"]


@then("mcp_servers 應為空")
def cfg_mcp_servers_empty(context):
    servers = context["cfg"].get("mcp_servers", [])
    # Either empty or only has legacy (non-registry) servers
    registry_servers = [s for s in servers if s.get("transport")]
    assert len(registry_servers) == 0
