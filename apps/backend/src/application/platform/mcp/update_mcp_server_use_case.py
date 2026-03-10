"""更新 MCP Server 註冊用例"""

from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.repository import McpServerRegistrationRepository
from src.domain.platform.value_objects import McpRegistryToolMeta
from src.domain.shared.exceptions import EntityNotFoundError

_SIMPLE_FIELDS = (
    "name", "description", "transport", "url", "command",
    "args", "required_env", "version", "scope", "tenant_ids", "is_enabled",
)


@dataclass(frozen=True)
class UpdateMcpServerCommand:
    server_id: str
    name: str | None = None
    description: str | None = None
    transport: str | None = None
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    required_env: list[str] | None = None
    available_tools: list[dict] | None = None
    version: str | None = None
    scope: str | None = None
    tenant_ids: list[str] | None = None
    is_enabled: bool | None = None


class UpdateMcpServerUseCase:
    def __init__(
        self,
        mcp_server_repository: McpServerRegistrationRepository,
    ) -> None:
        self._repo = mcp_server_repository

    async def execute(
        self, command: UpdateMcpServerCommand
    ) -> McpServerRegistration:
        server = await self._repo.find_by_id(command.server_id)
        if server is None:
            raise EntityNotFoundError(
                "McpServerRegistration", command.server_id
            )

        self._apply_updates(server, command)
        server.updated_at = datetime.now(timezone.utc)
        await self._repo.save(server)
        return server

    @staticmethod
    def _apply_updates(
        server: McpServerRegistration,
        command: UpdateMcpServerCommand,
    ) -> None:
        for field_name in _SIMPLE_FIELDS:
            value = getattr(command, field_name)
            if value is not None:
                setattr(server, field_name, value)

        if command.available_tools is not None:
            server.available_tools = [
                McpRegistryToolMeta(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                )
                for t in command.available_tools
            ]
