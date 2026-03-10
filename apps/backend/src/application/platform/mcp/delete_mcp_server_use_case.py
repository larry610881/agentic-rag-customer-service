"""刪除 MCP Server 註冊用例"""

from src.domain.platform.repository import McpServerRegistrationRepository


class DeleteMcpServerUseCase:
    def __init__(
        self,
        mcp_server_repository: McpServerRegistrationRepository,
    ) -> None:
        self._repo = mcp_server_repository

    async def execute(self, server_id: str) -> None:
        await self._repo.delete(server_id)
