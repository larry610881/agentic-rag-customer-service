"""MCP Tool Loader — 載入 MCP Server 工具

每次 ReAct 呼叫時建立新的 MCP session，
session 生命週期由呼叫端的 AsyncExitStack 管理。
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
        server_url: str,
        enabled_tools: list[str] | None = None,
    ) -> list[BaseTool]:
        """載入 MCP 工具，session 由 stack 管理生命週期。

        Args:
            stack: AsyncExitStack，管理 MCP session 生命週期
            server_url: MCP Server URL
            enabled_tools: 篩選特定工具名稱

        Returns:
            LangChain BaseTool 列表
        """
        return await self._connect_and_load(stack, server_url, enabled_tools)

    @staticmethod
    async def _connect_and_load(
        stack: AsyncExitStack,
        server_url: str,
        enabled_tools: list[str] | None = None,
    ) -> list[BaseTool]:
        """Connect to MCP server, keep session alive via exit stack."""
        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

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
                    server_url=server_url,
                    total=len(all_tools),
                    filtered=len(filtered),
                )
                return filtered

            logger.info(
                "mcp_loader.loaded",
                server_url=server_url,
                total=len(all_tools),
            )
            return all_tools
        except Exception as exc:
            logger.warning(
                "mcp_loader.connect_failed",
                server_url=server_url,
                error=str(exc),
            )
            return []

    def invalidate(self, server_url: str | None = None) -> None:
        """No-op — kept for API compatibility."""
