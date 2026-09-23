"""內嵌 MCP server 設定：請求 dict → McpServerConfig（建立與更新共用，Issue #103）。

過去建立與更新各自手寫一份組裝，兩份都漏了 transport / command / args，
stdio 型內嵌 server 因此一存就壞。集中在這裡，之後加欄位只改一處。

- 請求沒帶 transport / command / args（舊版前端）→ 沿用同名既有 server 的值
- url 與 args 在 API 回應時會遮罩憑證（#102）；送回遮罩值時保留原值
"""

from __future__ import annotations

from typing import Any

from src.domain.bot.entity import McpServerConfig, McpToolMeta
from src.domain.shared.secret_masking import keep_if_masked, mask_args, mask_url


def build_mcp_server_configs(
    raw_servers: list[dict[str, Any]],
    existing: list[McpServerConfig] | None = None,
) -> list[McpServerConfig]:
    by_name = {s.name: s for s in existing or []}
    return [
        _build_one(raw, by_name.get(raw.get("name", ""))) for raw in raw_servers
    ]


def _build_one(raw: dict[str, Any], old: McpServerConfig | None) -> McpServerConfig:
    old_url = old.url if old else ""
    old_args = list(old.args) if old else []
    args = list(raw["args"]) if "args" in raw else old_args
    return McpServerConfig(
        url=keep_if_masked(raw.get("url", ""), old_url, mask_url),
        name=raw.get("name", ""),
        enabled_tools=raw.get("enabled_tools", []),
        tools=[
            McpToolMeta(name=t.get("name", ""), description=t.get("description", ""))
            for t in raw.get("tools", [])
        ],
        version=raw.get("version", ""),
        transport=raw.get("transport") or (old.transport if old else "http"),
        command=raw["command"] if "command" in raw else (old.command if old else ""),
        args=keep_if_masked(args, old_args, mask_args),
    )
