"""MCP Tool Loader — 載入 MCP Server 工具

每次 ReAct 呼叫時建立新的 MCP session，
session 生命週期由呼叫端的 AsyncExitStack 管理。
支援 HTTP (streamable) 和 stdio 兩種 transport。
"""

from contextlib import AsyncExitStack

import structlog
from langchain_core.tools import BaseTool

logger = structlog.get_logger(__name__)


class CachedMCPToolLoader:
    """MCP 工具載入器（保留類名以相容 DI Container）"""

    async def load_tools(
        self,
        stack: AsyncExitStack,
        server_config: dict | str,
        enabled_tools: list[str] | None = None,
    ) -> list[BaseTool]:
        """載入 MCP 工具，session 由 stack 管理生命週期。

        Args:
            stack: AsyncExitStack，管理 MCP session 生命週期
            server_config: MCP Server config dict 或 legacy URL string
            enabled_tools: 篩選特定工具名稱

        Returns:
            LangChain BaseTool 列表
        """
        # Backward compat: accept plain URL string
        if isinstance(server_config, str):
            server_config = {"url": server_config, "transport": "http"}

        return await self._connect_and_load(stack, server_config, enabled_tools)

    @staticmethod
    async def _connect_and_load(
        stack: AsyncExitStack,
        server_config: dict,
        enabled_tools: list[str] | None = None,
    ) -> list[BaseTool]:
        """Connect to MCP server, keep session alive via exit stack."""
        transport = server_config.get("transport", "http")
        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
            from mcp import ClientSession

            if transport == "stdio":
                import os

                from mcp.client.stdio import StdioServerParameters, stdio_client

                read, write = await stack.enter_async_context(
                    stdio_client(
                        StdioServerParameters(
                            command=server_config["command"],
                            args=server_config.get("args", []),
                            env={**os.environ, **server_config.get("env", {})},
                        )
                    )
                )
            else:
                from mcp.client.streamable_http import streamablehttp_client

                server_url = server_config.get("url", "")
                read, write, _ = await stack.enter_async_context(
                    streamablehttp_client(server_url)
                )

            session = await stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            all_tools = await load_mcp_tools(session)

            if enabled_tools:
                filtered = [t for t in all_tools if t.name in enabled_tools]
                logger.info(
                    "mcp_loader.loaded",
                    transport=transport,
                    total=len(all_tools),
                    filtered=len(filtered),
                )
                return filtered

            logger.info(
                "mcp_loader.loaded",
                transport=transport,
                total=len(all_tools),
            )
            return all_tools
        except Exception as exc:
            logger.warning(
                "mcp_loader.connect_failed",
                transport=transport,
                server_config={k: v for k, v in server_config.items() if k != "env"},
                error=str(exc),
            )
            return []

    def invalidate(self, server_url: str | None = None) -> None:
        """No-op — kept for API compatibility."""
