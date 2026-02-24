"""刪除機器人用例"""

from src.domain.bot.repository import BotRepository
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteBotUseCase:
    def __init__(self, bot_repository: BotRepository) -> None:
        self._bot_repo = bot_repository

    async def execute(self, bot_id: str) -> None:
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", bot_id)
        await self._bot_repo.delete(bot_id)
