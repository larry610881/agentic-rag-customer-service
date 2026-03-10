"""測試 MCP Server 連線用例"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class McpConnectionResult:
    success: bool
    latency_ms: int = 0
    tools_count: int = 0
    error: str = ""


class TestMcpConnectionUseCase:
    async def execute(
        self,
        *,
        transport: str,
        url: str = "",
        command: str = "",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> McpConnectionResult:
        loop = asyncio.get_running_loop()
        t0 = time.monotonic()

        def _sync() -> McpConnectionResult:
            return asyncio.run(
                self._do_test(
                    transport=transport,
                    url=url,
                    command=command,
                    args=args,
                    env=env,
                )
            )

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                result = await loop.run_in_executor(pool, _sync)
            result.latency_ms = round((time.monotonic() - t0) * 1000)
            return result
        except Exception as exc:
            latency_ms = round((time.monotonic() - t0) * 1000)
            return McpConnectionResult(
                success=False,
                latency_ms=latency_ms,
                error=str(exc),
            )

    @staticmethod
    async def _do_test(
        *,
        transport: str,
        url: str,
        command: str,
        args: list[str] | None,
        env: dict[str, str] | None,
    ) -> McpConnectionResult:
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
            return McpConnectionResult(
                success=True,
                tools_count=len(resp.tools),
            )
