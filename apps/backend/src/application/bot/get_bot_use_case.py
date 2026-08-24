"""取得機器人用例"""

from src.application.bot._tenant_guard import ensure_bot_tenant
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.shared.exceptions import EntityNotFoundError


class GetBotUseCase:
    def __init__(self, bot_repository: BotRepository) -> None:
        self._bot_repo = bot_repository

    async def execute(
        self, bot_id: str, tenant_id: str | None = None, role: str | None = None
    ) -> Bot:
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", bot_id)
        # C8：跨租戶 → 404。tenant_id 為 None 代表呼叫端未帶入（維持舊行為），
        # 生產一律走 bot_router 且必帶 tenant_id（endpoint integration 測試釘住）。
        if tenant_id is not None:
            ensure_bot_tenant(bot, tenant_id, role)
        return bot
