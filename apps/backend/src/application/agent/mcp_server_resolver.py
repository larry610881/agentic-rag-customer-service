"""Bot 的 MCP server 設定解析（web / widget / LINE 共用，channel-parity）。

bot 上有兩種來源：
- 直接設定的 server（``bot.mcp_servers``）
- 綁定到 MCP Registry 的 server（``bot.mcp_bindings``）：查 registry、檢查租戶範圍、
  解密綁定的 env 值，http 類把 ``{KEY}`` 代換進 URL，stdio 類帶 command / args / env

規則沿用 web 管線原本的行為：registry 綁定解析出任何 server 時取代直接設定的
server；否則沿用直接設定的 server。
"""

from typing import Any

from src.domain.platform.services import EncryptionService


class McpServerResolver:
    def __init__(
        self,
        registry_repo: Any | None = None,
        encryption: EncryptionService | None = None,
    ) -> None:
        self._registry_repo = registry_repo
        self._encryption = encryption

    async def resolve(self, bot: Any, tenant_id: str) -> list[dict[str, Any]]:
        servers = self.inline_servers(bot)
        if bot.mcp_bindings and self._registry_repo:
            registry_servers = await self._resolve_registry(bot, tenant_id)
            if registry_servers:
                return registry_servers
        return servers

    @staticmethod
    def inline_servers(bot: Any) -> list[dict[str, Any]]:
        """bot 直接設定的 MCP server（非 registry binding）。"""
        return [
            {
                "url": s.url,
                "name": s.name,
                "enabled_tools": s.enabled_tools,
                "transport": s.transport,
                **(
                    {"command": s.command, "args": s.args}
                    if s.transport == "stdio"
                    else {}
                ),
            }
            for s in bot.mcp_servers
        ]

    def _decrypt_env_values(self, env_values: dict[str, str]) -> dict[str, str]:
        """Decrypt env_values (stored encrypted in DB)."""
        decrypted_env: dict[str, str] = {}
        for k, v in env_values.items():
            if not v:
                decrypted_env[k] = ""
            elif self._encryption:
                try:
                    decrypted_env[k] = self._encryption.decrypt(v)
                except Exception:
                    # Fallback: pre-migration plaintext data
                    decrypted_env[k] = v
            else:
                decrypted_env[k] = v
        return decrypted_env

    async def _resolve_registry(
        self, bot: Any, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Registry-based MCP bindings → resolved server configs."""
        assert self._registry_repo is not None
        registry_servers: list[dict[str, Any]] = []
        for binding in bot.mcp_bindings:
            reg = await self._registry_repo.find_by_id(binding.registry_id)
            if not reg or not reg.is_enabled:
                continue
            # Tenant scope check: skip if not accessible
            if reg.scope == "tenant" and tenant_id not in reg.tenant_ids:
                continue

            decrypted_env = self._decrypt_env_values(binding.env_values)

            server_cfg: dict[str, Any] = {
                "name": reg.name,
                "transport": reg.transport,
            }
            if reg.transport == "stdio":
                server_cfg["command"] = reg.command
                server_cfg["args"] = reg.args
                server_cfg["env"] = decrypted_env
            else:
                resolved_url = reg.url
                for key, value in decrypted_env.items():
                    resolved_url = resolved_url.replace(f"{{{key}}}", value)
                server_cfg["url"] = resolved_url
            if binding.enabled_tools:
                server_cfg["enabled_tools"] = binding.enabled_tools
            registry_servers.append(server_cfg)
        return registry_servers
