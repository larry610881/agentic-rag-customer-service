"""Regression：內嵌 stdio MCP server 建立、更新、回應都要保留 transport / command / args
（Issue #103）。

舊碼建立與更新只帶 url / name / tools，transport 落回 http、command 與 args 變空；
回應也不回這三欄 → stdio 型內嵌 server 建立即損壞，既有的按一次儲存就壞。
args 回應時走 #102 的憑證遮罩，存檔收到遮罩值要保留原值。
"""

import asyncio
from unittest.mock import AsyncMock

from src.application.bot.create_bot_use_case import CreateBotCommand, CreateBotUseCase
from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.domain.bot.entity import Bot, BotLLMParams, McpServerConfig
from src.domain.bot.value_objects import BotId
from src.interfaces.api import bot_router

STDIO = {
    "name": "fs",
    "url": "",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@mcp/filesystem", "--token", "tok-999"],
    "enabled_tools": ["read_file"],
}


def _stdio_bot() -> Bot:
    return Bot(
        id=BotId(value="b1"),
        tenant_id="t1",
        name="b",
        knowledge_base_ids=[],
        llm_params=BotLLMParams(),
        mcp_servers=[
            McpServerConfig(
                url="",
                name="fs",
                transport="stdio",
                command="npx",
                args=["-y", "@mcp/filesystem", "--token", "tok-999"],
            )
        ],
    )


def test_建立_bot_保留_stdio_的_transport_command_args():
    repo = AsyncMock()
    bot = asyncio.run(
        CreateBotUseCase(repo).execute(
            CreateBotCommand(tenant_id="t1", name="b", mcp_servers=[dict(STDIO)])
        )
    )
    (s,) = bot.mcp_servers
    assert (s.transport, s.command, s.args) == (
        "stdio",
        "npx",
        ["-y", "@mcp/filesystem", "--token", "tok-999"],
    )


def test_更新_bot_保留_stdio_的_transport_command_args():
    bot = _stdio_bot()
    UpdateBotUseCase._apply_updates(
        bot, UpdateBotCommand(bot_id="b1", mcp_servers=[dict(STDIO)])
    )
    (s,) = bot.mcp_servers
    assert (s.transport, s.command) == ("stdio", "npx")
    assert s.args == ["-y", "@mcp/filesystem", "--token", "tok-999"]


def test_bot_回應帶回三欄且_args_裡的憑證遮罩():
    (s,) = bot_router._to_response(_stdio_bot()).mcp_servers
    assert s["transport"] == "stdio"
    assert s["command"] == "npx"
    assert s["args"] == ["-y", "@mcp/filesystem", "--token", "***"]


def test_表單原封送回遮罩後的_args_保留原本的憑證():
    bot = _stdio_bot()
    returned = bot_router._to_response(bot).mcp_servers[0]
    UpdateBotUseCase._apply_updates(
        bot, UpdateBotCommand(bot_id="b1", mcp_servers=[dict(returned)])
    )
    assert bot.mcp_servers[0].args == ["-y", "@mcp/filesystem", "--token", "tok-999"]


def test_舊版前端沒送三欄時沿用同名_server_的原設定():
    """前端舊版表單只送 url / name：不能把既有 stdio server 洗成 http。"""
    bot = _stdio_bot()
    UpdateBotUseCase._apply_updates(
        bot, UpdateBotCommand(bot_id="b1", mcp_servers=[{"name": "fs", "url": ""}])
    )
    (s,) = bot.mcp_servers
    assert (s.transport, s.command) == ("stdio", "npx")
    assert s.args == ["-y", "@mcp/filesystem", "--token", "tok-999"]
