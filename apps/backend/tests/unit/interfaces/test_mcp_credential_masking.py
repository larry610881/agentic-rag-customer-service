"""Regression：MCP 網址與 stdio 參數的憑證不得原樣出現在 API 回應（Issue #102）。

- bot 回應的 mcp_servers[].url
- MCP registry 回應的 url / args（租戶帳號可讀清單與單筆）
遮罩後的值被表單原封送回存檔時，必須保留原本的憑證，不可把 *** 存進去。
"""

from unittest.mock import AsyncMock

from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.application.platform.mcp.update_mcp_server_use_case import (
    UpdateMcpServerCommand,
    UpdateMcpServerUseCase,
)
from src.domain.bot.entity import Bot, BotLLMParams, McpServerConfig
from src.domain.bot.value_objects import BotId
from src.domain.platform.entity import McpServerRegistration
from src.interfaces.api import bot_router, mcp_server_router

SECRET_URL = "https://mcp.example.com/sse?api_key=sk-live-123&region=tw"
MASKED_URL = "https://mcp.example.com/sse?api_key=***&region=tw"
SECRET_ARGS = ["--token", "tok-999", "--port", "8080"]
MASKED_ARGS = ["--token", "***", "--port", "8080"]


def _bot() -> Bot:
    return Bot(
        id=BotId(value="b1"),
        tenant_id="t1",
        name="b",
        knowledge_base_ids=[],
        llm_params=BotLLMParams(),
        mcp_servers=[McpServerConfig(url=SECRET_URL, name="shop")],
    )


def _registration() -> McpServerRegistration:
    return McpServerRegistration(
        name="shop",
        transport="stdio",
        url=SECRET_URL,
        command="npx",
        args=list(SECRET_ARGS),
    )


def test_bot_回應遮罩_mcp_網址裡的憑證():
    resp = bot_router._to_response(_bot())
    assert resp.mcp_servers[0]["url"] == MASKED_URL
    assert "sk-live-123" not in resp.model_dump_json()


def test_bot_存檔時送回遮罩網址_保留原本的憑證():
    bot = _bot()
    command = UpdateBotCommand(
        bot_id="b1",
        mcp_servers=[{"url": MASKED_URL, "name": "shop"}],
    )
    UpdateBotUseCase._apply_updates(bot, command)
    assert bot.mcp_servers[0].url == SECRET_URL


def test_bot_存檔時真的改了網址_採用新值():
    bot = _bot()
    new_url = "https://mcp.example.com/sse?api_key=sk-live-456"
    command = UpdateBotCommand(
        bot_id="b1", mcp_servers=[{"url": new_url, "name": "shop"}]
    )
    UpdateBotUseCase._apply_updates(bot, command)
    assert bot.mcp_servers[0].url == new_url


def test_registry_回應遮罩網址與參數():
    resp = mcp_server_router._to_response(_registration())
    assert resp.url == MASKED_URL
    assert resp.args == MASKED_ARGS
    dumped = resp.model_dump_json()
    assert "sk-live-123" not in dumped and "tok-999" not in dumped


def test_registry_存檔時送回遮罩值_保留原本的憑證():
    import asyncio

    server = _registration()
    repo = AsyncMock()
    repo.find_by_id.return_value = server
    asyncio.run(
        UpdateMcpServerUseCase(repo).execute(
            UpdateMcpServerCommand(
                server_id="x", url=MASKED_URL, args=list(MASKED_ARGS)
            )
        )
    )
    assert server.url == SECRET_URL
    assert server.args == SECRET_ARGS
