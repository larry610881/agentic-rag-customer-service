"""WorkerConfig Repository 介面"""

from abc import ABC, abstractmethod

from src.domain.bot.worker_config import WorkerConfig


class WorkerConfigRepository(ABC):
    @abstractmethod
    async def save(self, worker: WorkerConfig) -> None: ...

    @abstractmethod
    async def find_by_bot_id(
        self, bot_id: str
    ) -> list[WorkerConfig]: ...

    @abstractmethod
    async def find_by_id(
        self, worker_id: str
    ) -> WorkerConfig | None: ...

    @abstractmethod
    async def delete(self, worker_id: str) -> None: ...
