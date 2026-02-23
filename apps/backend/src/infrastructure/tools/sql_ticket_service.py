"""SQL 客服工單服務"""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.agent.tool_services import TicketService
from src.domain.agent.value_objects import ToolResult
from src.infrastructure.db.models.ticket_model import TicketModel


class SQLTicketService(TicketService):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_ticket(
        self,
        tenant_id: str,
        subject: str,
        description: str,
        order_id: str = "",
    ) -> ToolResult:
        ticket_id = str(uuid4())
        ticket = TicketModel(
            id=ticket_id,
            tenant_id=tenant_id,
            subject=subject,
            description=description,
            order_id=order_id,
            status="open",
        )

        async with self._session_factory() as session:
            session.add(ticket)
            await session.commit()

        return ToolResult(
            tool_name="ticket_creation",
            success=True,
            data={
                "ticket_id": ticket_id,
                "tenant_id": tenant_id,
                "subject": subject,
                "order_id": order_id,
                "status": "open",
            },
        )
