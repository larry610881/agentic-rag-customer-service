"""列出機器人用例"""

from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository


class ListBotsUseCase:
    def __init__(self, bot_repository: BotRepository) -> None:
        self._bot_repo = bot_repository

    async def execute(self, tenant_id: str) -> list[Bot]:
        return await self._bot_repo.find_all_by_tenant(tenant_id)
