"""Cached MCP Tool Loader — 快取 MCP Server 工具載入

避免每次 ReAct 呼叫都重新建立 SSE 連線，
以 server_url 為 key 快取 BaseTool 列表，TTL 預設 5 分鐘。
"""

import asyncio
import time
from typing import Any

import structlog
from langchain_core.tools import BaseTool

logger = structlog.get_logger(__name__)

_DEFAULT_TTL = 300  # 5 minutes


class CachedMCPToolLoader:
    """MCP 工具快取載入器（Singleton 生命週期）"""

    def __init__(self, ttl: int = _DEFAULT_TTL) -> None:
        self._ttl = ttl
        self._cache: dict[str, tuple[list[BaseTool], float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def load_tools(
        self,
        server_url: str,
        enabled_tools: list[str] | None = None,
    ) -> list[BaseTool]:
        """載入 MCP 工具（有快取則直接回傳）。

        Args:
            server_url: MCP Server URL
            enabled_tools: 篩選特定工具名稱

        Returns:
            LangChain BaseTool 列表
        """
        cache_key = server_url

        # Check cache (without lock for fast path)
        if cache_key in self._cache:
            tools, cached_at = self._cache[cache_key]
            if time.monotonic() - cached_at < self._ttl:
                filtered = self._filter_tools(tools, enabled_tools)
                logger.debug(
                    "mcp_cache.hit",
                    server_url=server_url,
                    total=len(tools),
                    filtered=len(filtered),
                )
                return filtered

        # Cache miss — acquire lock to avoid concurrent connections
        lock = self._get_lock(cache_key)
        async with lock:
            # Double-check after acquiring lock
            if cache_key in self._cache:
                tools, cached_at = self._cache[cache_key]
                if time.monotonic() - cached_at < self._ttl:
                    return self._filter_tools(tools, enabled_tools)

            # Load from MCP server
            tools = await self._connect_and_load(server_url)
            self._cache[cache_key] = (tools, time.monotonic())

            filtered = self._filter_tools(tools, enabled_tools)
            logger.info(
                "mcp_cache.loaded",
                server_url=server_url,
                total=len(tools),
                filtered=len(filtered),
            )
            return filtered

    @staticmethod
    async def _connect_and_load(server_url: str) -> list[BaseTool]:
        """Connect to MCP server and load all tools."""
        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await load_mcp_tools(session)
        except Exception as exc:
            logger.warning(
                "mcp_cache.connect_failed",
                server_url=server_url,
                error=str(exc),
            )
            return []

    @staticmethod
    def _filter_tools(
        tools: list[BaseTool],
        enabled_tools: list[str] | None,
    ) -> list[BaseTool]:
        if not enabled_tools:
            return tools
        return [t for t in tools if t.name in enabled_tools]

    def invalidate(self, server_url: str | None = None) -> None:
        """Invalidate cache for a specific server or all servers."""
        if server_url:
            self._cache.pop(server_url, None)
        else:
            self._cache.clear()
