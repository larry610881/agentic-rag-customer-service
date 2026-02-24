"""LINE Webhook 處理 Use Case"""

from src.domain.agent.services import AgentService
from src.domain.line.entity import LineTextMessageEvent
from src.domain.line.services import LineMessagingService


class HandleWebhookUseCase:
    def __init__(
        self,
        agent_service: AgentService,
        line_messaging_service: LineMessagingService,
        default_tenant_id: str,
        default_kb_id: str,
    ):
        self._agent_service = agent_service
        self._line_service = line_messaging_service
        self._default_tenant_id = default_tenant_id
        self._default_kb_id = default_kb_id

    async def execute(self, events: list[LineTextMessageEvent]) -> None:
        for event in events:
            if not event.message_text:
                continue
            result = await self._agent_service.process_message(
                tenant_id=self._default_tenant_id,
                kb_id=self._default_kb_id,
                user_message=event.message_text,
                kb_ids=[self._default_kb_id],
            )
            await self._line_service.reply_text(event.reply_token, result.answer)
