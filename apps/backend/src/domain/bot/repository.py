from abc import ABC, abstractmethod

from src.domain.bot.entity import Bot


class BotRepository(ABC):
    @abstractmethod
    async def save(self, bot: Bot) -> None: ...

    @abstractmethod
    async def find_by_id(self, bot_id: str) -> Bot | None: ...

    @abstractmethod
    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Bot]: ...

    @abstractmethod
    async def find_all(
        self,
        *,
        tenant_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Bot]: ...

    @abstractmethod
    async def count_by_tenant(self, tenant_id: str) -> int: ...

    @abstractmethod
    async def count_all(
        self, *, tenant_id: str | None = None
    ) -> int: ...

    @abstractmethod
    async def find_by_short_code(self, short_code: str) -> Bot | None: ...

    @abstractmethod
    async def delete(self, bot_id: str) -> None: ...

    async def exists_for_tenant(
        self, bot_id: str, tenant_id: str
    ) -> bool:
        """Return True 若 bot 屬於指定 tenant。預設以 find_by_id fallback，
        SQLAlchemy 實作會覆寫成輕量 SELECT 1 查詢。"""
        bot = await self.find_by_id(bot_id)
        return bot is not None and bot.tenant_id == tenant_id
