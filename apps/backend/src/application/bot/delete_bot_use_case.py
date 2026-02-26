"""刪除機器人用例"""

from src.domain.bot.repository import BotRepository
from src.domain.shared.cache_service import CacheService
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteBotUseCase:
    def __init__(
        self,
        bot_repository: BotRepository,
        cache_service: CacheService | None = None,
    ) -> None:
        self._bot_repo = bot_repository
        self._cache_service = cache_service

    async def execute(self, bot_id: str) -> None:
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", bot_id)
        await self._bot_repo.delete(bot_id)
        if self._cache_service is not None:
            await self._cache_service.delete(f"bot:{bot_id}")
