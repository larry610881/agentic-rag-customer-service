"""MCP Server Registry API 端點"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.platform.mcp.create_mcp_server_use_case import (
    CreateMcpServerCommand,
    CreateMcpServerUseCase,
)
from src.application.platform.mcp.delete_mcp_server_use_case import (
    DeleteMcpServerUseCase,
)
from src.application.platform.mcp.discover_mcp_server_use_case import (
    DiscoverMcpServerUseCase,
)
from src.application.platform.mcp.test_connection_use_case import (
    TestMcpConnectionUseCase,
)
from src.application.platform.mcp.update_mcp_server_use_case import (
    UpdateMcpServerCommand,
    UpdateMcpServerUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import (
    DomainException,
    DuplicateEntityError,
    EntityNotFoundError,
)

router = APIRouter(prefix="/api/v1/mcp-servers", tags=["mcp-registry"])


# --- Schemas ---

class ToolMetaSchema(BaseModel):
    name: str
    description: str = ""


class CreateMcpServerRequest(BaseModel):
    name: str
    description: str = ""
    transport: str = "http"
    url: str = ""
    command: str = ""
    args: list[str] = []
    required_env: list[str] = []
    available_tools: list[ToolMetaSchema] = []
    version: str = ""
    scope: str = "global"
    tenant_ids: list[str] = []


class UpdateMcpServerRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    transport: str | None = None
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    required_env: list[str] | None = None
    available_tools: list[ToolMetaSchema] | None = None
    version: str | None = None
    scope: str | None = None
    tenant_ids: list[str] | None = None
    is_enabled: bool | None = None


class McpServerResponse(BaseModel):
    id: str
    name: str
    description: str
    transport: str
    url: str
    command: str
    args: list[str]
    required_env: list[str]
    available_tools: list[ToolMetaSchema]
    version: str
    scope: str
    tenant_ids: list[str]
    is_enabled: bool
    created_at: str
    updated_at: str


class DiscoverRequest(BaseModel):
    transport: str = "http"
    url: str = ""
    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    server_id: str = ""


class TestConnectionRequest(BaseModel):
    transport: str = "http"
    url: str = ""
    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}


class TestConnectionResponse(BaseModel):
    success: bool
    latency_ms: int = 0
    tools_count: int = 0
    error: str = ""


# --- Helpers ---

def _to_response(server: Any) -> McpServerResponse:
    return McpServerResponse(
        id=server.id.value,
        name=server.name,
        description=server.description,
        transport=server.transport,
        url=server.url,
        command=server.command,
        args=server.args,
        required_env=server.required_env,
        available_tools=[
            ToolMetaSchema(name=t.name, description=t.description)
            for t in server.available_tools
        ],
        version=server.version,
        scope=server.scope,
        tenant_ids=server.tenant_ids,
        is_enabled=server.is_enabled,
        created_at=server.created_at.isoformat(),
        updated_at=server.updated_at.isoformat(),
    )


# --- Endpoints ---

@router.post(
    "",
    response_model=McpServerResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_mcp_server(
    body: CreateMcpServerRequest,
    use_case: CreateMcpServerUseCase = Depends(
        Provide[Container.create_mcp_server_use_case]
    ),
) -> McpServerResponse:
    try:
        server = await use_case.execute(
            CreateMcpServerCommand(
                name=body.name,
                description=body.description,
                transport=body.transport,
                url=body.url,
                command=body.command,
                args=body.args,
                required_env=body.required_env,
                available_tools=[t.model_dump() for t in body.available_tools],
                version=body.version,
                scope=body.scope,
                tenant_ids=body.tenant_ids,
            )
        )
    except DuplicateEntityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        ) from None
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from None
    return _to_response(server)


@router.get("", response_model=list[McpServerResponse])
@inject
async def list_mcp_servers(
    use_case: CreateMcpServerUseCase = Depends(
        Provide[Container.create_mcp_server_use_case]
    ),
    repo: Any = Depends(Provide[Container.mcp_server_repository]),
) -> list[McpServerResponse]:
    servers = await repo.find_all()
    return [_to_response(s) for s in servers]


@router.get("/{server_id}", response_model=McpServerResponse)
@inject
async def get_mcp_server(
    server_id: str,
    repo: Any = Depends(Provide[Container.mcp_server_repository]),
) -> McpServerResponse:
    server = await repo.find_by_id(server_id)
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"McpServerRegistration with id '{server_id}' not found",
        )
    return _to_response(server)


@router.put("/{server_id}", response_model=McpServerResponse)
@inject
async def update_mcp_server(
    server_id: str,
    body: UpdateMcpServerRequest,
    use_case: UpdateMcpServerUseCase = Depends(
        Provide[Container.update_mcp_server_use_case]
    ),
) -> McpServerResponse:
    try:
        server = await use_case.execute(
            UpdateMcpServerCommand(
                server_id=server_id,
                name=body.name,
                description=body.description,
                transport=body.transport,
                url=body.url,
                command=body.command,
                args=body.args,
                required_env=body.required_env,
                available_tools=(
                    [t.model_dump() for t in body.available_tools]
                    if body.available_tools is not None
                    else None
                ),
                version=body.version,
                scope=body.scope,
                tenant_ids=body.tenant_ids,
                is_enabled=body.is_enabled,
            )
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    return _to_response(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_mcp_server(
    server_id: str,
    use_case: DeleteMcpServerUseCase = Depends(
        Provide[Container.delete_mcp_server_use_case]
    ),
) -> None:
    await use_case.execute(server_id)


@router.post("/discover", response_model=list[ToolMetaSchema])
@inject
async def discover_tools(
    body: DiscoverRequest,
    use_case: DiscoverMcpServerUseCase = Depends(
        Provide[Container.discover_mcp_server_use_case]
    ),
) -> list[ToolMetaSchema]:
    try:
        tools = await use_case.execute(
            transport=body.transport,
            url=body.url,
            command=body.command,
            args=body.args,
            env=body.env,
            server_id=body.server_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to discover tools: {e}",
        ) from None
    return [ToolMetaSchema(name=t.name, description=t.description) for t in tools]


@router.post(
    "/{server_id}/test-connection",
    response_model=TestConnectionResponse,
)
@inject
async def test_mcp_connection(
    server_id: str,
    use_case: TestMcpConnectionUseCase = Depends(
        Provide[Container.test_mcp_connection_use_case]
    ),
    repo: Any = Depends(Provide[Container.mcp_server_repository]),
) -> TestConnectionResponse:
    server = await repo.find_by_id(server_id)
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"McpServerRegistration with id '{server_id}' not found",
        )
    result = await use_case.execute(
        transport=server.transport,
        url=server.url,
        command=server.command,
        args=server.args,
    )
    return TestConnectionResponse(
        success=result.success,
        latency_ms=result.latency_ms,
        tools_count=result.tools_count,
        error=result.error,
    )
