"""MCP Binding env_values Encryption BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.bot.create_bot_use_case import (
    CreateBotCommand,
    CreateBotUseCase,
)
from src.domain.bot.entity import Bot, BotMcpBinding
from src.domain.bot.repository import BotRepository
from src.domain.conversation.repository import ConversationRepository
from src.domain.platform.services import EncryptionService

scenarios("unit/bot/env_values_encryption.feature")


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
def mock_encryption():
    enc = MagicMock(spec=EncryptionService)
    enc.encrypt.side_effect = lambda v: f"ENC({v})"
    enc.decrypt.side_effect = lambda v: v.replace("ENC(", "").replace(")", "")
    return enc


# --- Scenario 1: 建立 Bot 時加密 env_values ---


@given("一個帶有 MCP binding env_values 的建立指令")
def setup_create_command(context, mock_encryption):
    mock_repo = AsyncMock(spec=BotRepository)
    mock_repo.save = AsyncMock()
    context["mock_repo"] = mock_repo
    context["use_case"] = CreateBotUseCase(
        bot_repository=mock_repo,
        encryption_service=mock_encryption,
    )
    context["command"] = CreateBotCommand(
        tenant_id="t-1",
        name="TestBot",
        mcp_bindings=[
            {
                "registry_id": "reg-1",
                "enabled_tools": ["tool_a"],
                "env_values": {"API_KEY": "sk-secret-123"},
            }
        ],
    )


@when("執行 CreateBotUseCase")
def run_create(context):
    context["result"] = _run(context["use_case"].execute(context["command"]))


@then("存入 Repository 的 env_values 值應為加密字串")
def verify_encrypted_env(context):
    bot = context["result"]
    assert len(bot.mcp_bindings) == 1
    env = bot.mcp_bindings[0].env_values
    # The mock encrypts as "ENC(value)"
    assert env["API_KEY"] == "ENC(sk-secret-123)"


# --- Scenario 2: Agent 處理訊息時解密 env_values ---


@given("一個 Bot 帶有加密的 mcp_binding env_values")
def setup_bot_with_encrypted_bindings(context, mock_encryption):
    bot = Bot(
        tenant_id="t-1",
        name="TestBot",
        mcp_bindings=[
            BotMcpBinding(
                registry_id="reg-1",
                enabled_tools=[],
                env_values={"API_KEY": "ENC(sk-secret-123)"},
            )
        ],
    )
    mock_bot_repo = AsyncMock(spec=BotRepository)
    mock_bot_repo.find_by_id.return_value = bot

    mock_conv_repo = AsyncMock(spec=ConversationRepository)
    mock_conv_repo.find_by_id.return_value = None

    # Mock MCP registry repo
    mock_reg = MagicMock()
    mock_reg.name = "test-server"
    mock_reg.transport = "sse"
    mock_reg.url = "https://api.example.com/{API_KEY}/endpoint"
    mock_reg.is_enabled = True
    mock_mcp_repo = AsyncMock()
    mock_mcp_repo.find_by_id.return_value = mock_reg

    context["mock_encryption"] = mock_encryption
    context["mock_bot_repo"] = mock_bot_repo
    context["mock_conv_repo"] = mock_conv_repo
    context["mock_mcp_repo"] = mock_mcp_repo


@when("SendMessageUseCase 解析 mcp_bindings")
def run_load_bot_config(context):
    mock_agent = AsyncMock()
    use_case = SendMessageUseCase(
        agent_service=mock_agent,
        conversation_repository=context["mock_conv_repo"],
        bot_repository=context["mock_bot_repo"],
        mcp_registry_repo=context["mock_mcp_repo"],
        encryption_service=context["mock_encryption"],
    )
    command = SendMessageCommand(
        tenant_id="t-1",
        bot_id="bot-1",
        message="hello",
    )
    cfg = _run(use_case._load_bot_config(command))
    context["cfg"] = cfg


@then("URL 模板應使用解密後的值替換")
def verify_decrypted_url(context):
    cfg = context["cfg"]
    servers = cfg.get("mcp_servers", [])
    assert len(servers) == 1
    # ENC(sk-secret-123) → decrypted to sk-secret-123
    assert servers[0]["url"] == "https://api.example.com/sk-secret-123/endpoint"
