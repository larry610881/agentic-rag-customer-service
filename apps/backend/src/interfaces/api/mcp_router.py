"""MCP Discovery Router — 連線 MCP Server 取得 Tools 清單"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.interfaces.api.deps import CurrentTenant, get_current_tenant

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


class DiscoverRequest(BaseModel):
    url: str


class McpToolParam(BaseModel):
    name: str
    type: str
    description: str
    required: bool
    default: Any = None


class McpToolInfo(BaseModel):
    name: str
    description: str
    parameters: list[McpToolParam]


class DiscoverResponse(BaseModel):
    server_name: str
    tools: list[McpToolInfo]


def _parse_json_schema_properties(
    input_schema: dict[str, Any],
) -> list[McpToolParam]:
    """Parse JSON Schema properties into McpToolParam list."""
    properties = input_schema.get("properties", {})
    required_fields = set(input_schema.get("required", []))
    params: list[McpToolParam] = []

    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        if isinstance(prop_type, list):
            # Handle union types like ["string", "null"]
            prop_type = next(
                (t for t in prop_type if t != "null"), "string"
            )
        params.append(
            McpToolParam(
                name=prop_name,
                type=prop_type,
                description=prop_schema.get("description", ""),
                required=prop_name in required_fields,
                default=prop_schema.get("default"),
            )
        )

    return params


async def _discover_tools(url: str) -> DiscoverResponse:
    """Run MCP discovery in a standalone asyncio.run() to avoid
    TaskGroup nesting issues with uvicorn's event loop."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    def _sync_discover() -> DiscoverResponse:
        return asyncio.run(_do_discover(url))

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return await loop.run_in_executor(pool, _sync_discover)


async def _do_discover(url: str) -> DiscoverResponse:
    """Actual MCP discovery logic — runs in its own event loop."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            response = await session.list_tools()

            tools: list[McpToolInfo] = []
            for tool in response.tools:
                params = _parse_json_schema_properties(
                    tool.inputSchema if tool.inputSchema else {}
                )
                tools.append(
                    McpToolInfo(
                        name=tool.name,
                        description=tool.description or "",
                        parameters=params,
                    )
                )

            server_name = (
                init_result.serverInfo.name
                if init_result.serverInfo
                else "unknown"
            )

            return DiscoverResponse(
                server_name=server_name,
                tools=tools,
            )


@router.post("/discover", response_model=DiscoverResponse)
async def discover_mcp_tools(
    request: DiscoverRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
) -> DiscoverResponse:
    """連線 MCP Server，回傳可用的 Tools 清單。"""
    try:
        result = await _discover_tools(request.url)
        logger.info(
            "mcp.discover.success",
            url=request.url,
            tool_count=len(result.tools),
            server_name=result.server_name,
        )
        return result

    except Exception as exc:
        logger.warning(
            "mcp.discover.failed",
            url=request.url,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail=f"無法連線 MCP Server: {exc}",
        ) from exc
