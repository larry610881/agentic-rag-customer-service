from abc import ABC, abstractmethod

from src.domain.bot.entity import Bot


class BotRepository(ABC):
    @abstractmethod
    async def save(self, bot: Bot) -> None: ...

    @abstractmethod
    async def find_by_id(self, bot_id: str) -> Bot | None: ...

    @abstractmethod
    async def find_all_by_tenant(self, tenant_id: str) -> list[Bot]: ...

    @abstractmethod
    async def delete(self, bot_id: str) -> None: ...
