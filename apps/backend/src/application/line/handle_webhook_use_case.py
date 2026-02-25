"""LINE Webhook 處理 Use Case"""

from src.domain.agent.services import AgentService
from src.domain.bot.repository import BotRepository
from src.domain.line.entity import LineTextMessageEvent
from src.domain.line.services import LineMessagingService, LineMessagingServiceFactory


class HandleWebhookUseCase:
    def __init__(
        self,
        agent_service: AgentService,
        bot_repository: BotRepository,
        line_service_factory: LineMessagingServiceFactory,
        default_line_service: LineMessagingService | None = None,
        default_tenant_id: str = "",
        default_kb_id: str = "",
    ):
        self._agent_service = agent_service
        self._bot_repository = bot_repository
        self._line_service_factory = line_service_factory
        self._default_line_service = default_line_service
        self._default_tenant_id = default_tenant_id
        self._default_kb_id = default_kb_id

    async def execute(self, events: list[LineTextMessageEvent]) -> None:
        """舊端點：使用預設租戶設定處理 Webhook 事件。"""
        if not self._default_line_service:
            return
        for event in events:
            if not event.message_text:
                continue
            result = await self._agent_service.process_message(
                tenant_id=self._default_tenant_id,
                kb_id=self._default_kb_id,
                user_message=event.message_text,
                kb_ids=[self._default_kb_id],
            )
            await self._default_line_service.reply_text(
                event.reply_token, result.answer
            )

    async def execute_for_bot(
        self,
        bot_id: str,
        body_text: str,
        signature: str,
        events: list[LineTextMessageEvent],
    ) -> None:
        """新端點：根據 Bot ID 路由到正確租戶處理 Webhook 事件。"""
        bot = await self._bot_repository.find_by_id(bot_id)
        if bot is None:
            raise ValueError(f"Bot not found: {bot_id}")

        if not bot.line_channel_secret:
            raise ValueError(
                f"Bot {bot_id} has no LINE channel secret configured"
            )

        line_service = self._line_service_factory.create(
            bot.line_channel_secret,
            bot.line_channel_access_token or "",
        )

        if not await line_service.verify_signature(body_text, signature):
            raise ValueError("Invalid LINE webhook signature")

        for event in events:
            if not event.message_text:
                continue
            result = await self._agent_service.process_message(
                tenant_id=bot.tenant_id,
                kb_id=bot.knowledge_base_ids[0] if bot.knowledge_base_ids else "",
                user_message=event.message_text,
                kb_ids=bot.knowledge_base_ids,
                system_prompt=bot.system_prompt or None,
            )
            await line_service.reply_text(event.reply_token, result.answer)
