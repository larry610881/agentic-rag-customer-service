"""Regression：LINE 通路解析 MCP registry 綁定（Issue #100 B4）。

舊碼讀 BotMcpBinding.url / .transport，但該 value object 只有
registry_id / enabled_tools / env_values → 綁了 MCP 的 bot 在 LINE 收訊息即
AttributeError（引入於 96489d7）。修法依 channel-parity：LINE 改用與 web
相同的共用解析（查 registry、租戶範圍檢查、env 代換 URL）。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.bot.entity import Bot, BotLLMParams, BotMcpBinding
from src.domain.bot.value_objects import BotId


def _bot_with_binding() -> Bot:
    return Bot(
        id=BotId(value="b1"),
        tenant_id="t1",
        name="b",
        knowledge_base_ids=["kb-1"],
        llm_params=BotLLMParams(),
        mcp_bindings=[
            BotMcpBinding(
                registry_id="reg-1",
                enabled_tools=["search"],
                env_values={"TOKEN": "abc"},
            )
        ],
    )


def test_LINE_解析_registry_綁定成與_web_相同的_server_設定():
    registry = AsyncMock()
    registry.find_by_id.return_value = SimpleNamespace(
        name="商品查詢",
        transport="http",
        url="https://mcp.example/{TOKEN}",
        command="",
        args=[],
        scope="global",
        tenant_ids=[],
        is_enabled=True,
    )
    uc = HandleWebhookUseCase(
        agent_service=MagicMock(),
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        mcp_registry_repo=registry,
    )

    servers = asyncio.run(uc._line_mcp_servers(_bot_with_binding()))

    assert servers == [
        {
            "name": "商品查詢",
            "transport": "http",
            "url": "https://mcp.example/abc",
            "enabled_tools": ["search"],
        }
    ]
    registry.find_by_id.assert_awaited_once_with("reg-1")
