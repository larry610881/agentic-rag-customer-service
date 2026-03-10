"""探索 MCP Server 工具列表用例

使用 ThreadPoolExecutor + asyncio.run() 避免 TaskGroup 巢狀問題。
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import structlog

from src.domain.platform.repository import McpServerRegistrationRepository
from src.domain.platform.value_objects import McpRegistryToolMeta

logger = structlog.get_logger(__name__)


class DiscoverMcpServerUseCase:
    def __init__(
        self,
        mcp_server_repository: McpServerRegistrationRepository | None = None,
    ) -> None:
        self._repo = mcp_server_repository

    async def execute(
        self,
        *,
        transport: str,
        url: str = "",
        command: str = "",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        server_id: str = "",
    ) -> list[McpRegistryToolMeta]:
        loop = asyncio.get_running_loop()

        def _sync() -> list[McpRegistryToolMeta]:
            return asyncio.run(
                self._do_discover(
                    transport=transport,
                    url=url,
                    command=command,
                    args=args,
                    env=env,
                )
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            tools = await loop.run_in_executor(pool, _sync)

        # Write back to registry if server_id provided
        if server_id and self._repo:
            reg = await self._repo.find_by_id(server_id)
            if reg:
                reg.available_tools = tools
                reg.updated_at = datetime.now(timezone.utc)
                await self._repo.save(reg)

        return tools

    @staticmethod
    async def _do_discover(
        *,
        transport: str,
        url: str,
        command: str,
        args: list[str] | None,
        env: dict[str, str] | None,
    ) -> list[McpRegistryToolMeta]:
        from contextlib import AsyncExitStack

        from mcp import ClientSession

        async with AsyncExitStack() as stack:
            if transport == "stdio":
                import os

                from mcp.client.stdio import StdioServerParameters, stdio_client

                read, write = await stack.enter_async_context(
                    stdio_client(
                        StdioServerParameters(
                            command=command,
                            args=args or [],
                            env={**os.environ, **(env or {})},
                        )
                    )
                )
            else:
                from mcp.client.streamable_http import streamablehttp_client

                read, write, _ = await stack.enter_async_context(
                    streamablehttp_client(url)
                )

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            resp = await session.list_tools()
            return [
                McpRegistryToolMeta(name=t.name, description=t.description or "")
                for t in resp.tools
            ]
