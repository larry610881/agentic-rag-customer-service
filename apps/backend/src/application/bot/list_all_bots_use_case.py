"""列出所有租戶的機器人（跨租戶總覽，可選租戶篩選）"""

from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository


class ListAllBotsUseCase:
    def __init__(self, bot_repository: BotRepository) -> None:
        self._bot_repo = bot_repository

    async def execute(self, tenant_id: str | None = None) -> list[Bot]:
        if tenant_id:
            return await self._bot_repo.find_all_by_tenant(tenant_id)
        return await self._bot_repo.find_all()
