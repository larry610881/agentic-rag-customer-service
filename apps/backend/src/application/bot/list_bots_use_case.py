"""列出機器人用例"""

from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository


class ListBotsUseCase:
    def __init__(self, bot_repository: BotRepository) -> None:
        self._bot_repo = bot_repository

    async def execute(
        self,
        tenant_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Bot]:
        return await self._bot_repo.find_all_by_tenant(
            tenant_id, limit=limit, offset=offset,
        )

    async def count(self, tenant_id: str) -> int:
        return await self._bot_repo.count_by_tenant(tenant_id)
