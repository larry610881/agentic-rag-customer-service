"""建立 MCP Server 註冊用例"""

from dataclasses import dataclass

from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.repository import McpServerRegistrationRepository
from src.domain.platform.value_objects import McpRegistryId, McpRegistryToolMeta
from src.domain.shared.exceptions import DomainException, DuplicateEntityError


@dataclass(frozen=True)
class CreateMcpServerCommand:
    name: str
    description: str = ""
    transport: str = "http"
    url: str = ""
    command: str = ""
    args: list[str] | None = None
    required_env: list[str] | None = None
    available_tools: list[dict] | None = None
    version: str = ""
    scope: str = "global"
    tenant_ids: list[str] | None = None


class CreateMcpServerUseCase:
    def __init__(
        self,
        mcp_server_repository: McpServerRegistrationRepository,
    ) -> None:
        self._repo = mcp_server_repository

    async def execute(
        self, command: CreateMcpServerCommand
    ) -> McpServerRegistration:
        # Validate transport-specific fields
        if command.transport == "http":
            if not command.url:
                raise DomainException("HTTP transport requires a URL")
            existing = await self._repo.find_by_url(command.url)
            if existing:
                raise DuplicateEntityError(
                    "McpServerRegistration", "url", command.url
                )
        elif command.transport == "stdio":
            if not command.command:
                raise DomainException("stdio transport requires a command")

        tools = [
            McpRegistryToolMeta(
                name=t.get("name", ""),
                description=t.get("description", ""),
            )
            for t in (command.available_tools or [])
        ]

        server = McpServerRegistration(
            id=McpRegistryId(),
            name=command.name,
            description=command.description,
            transport=command.transport,
            url=command.url,
            command=command.command,
            args=command.args or [],
            required_env=command.required_env or [],
            available_tools=tools,
            version=command.version,
            scope=command.scope,
            tenant_ids=command.tenant_ids or [],
        )
        await self._repo.save(server)
        return server
