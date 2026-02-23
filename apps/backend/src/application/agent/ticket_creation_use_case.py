"""客服工單建立用例"""

from src.domain.agent.tool_services import TicketService
from src.domain.agent.value_objects import ToolResult


class TicketCreationUseCase:
    def __init__(self, ticket_service: TicketService) -> None:
        self._service = ticket_service

    async def execute(
        self,
        tenant_id: str,
        subject: str,
        description: str,
        order_id: str = "",
    ) -> ToolResult:
        return await self._service.create_ticket(
            tenant_id=tenant_id,
            subject=subject,
            description=description,
            order_id=order_id,
        )
