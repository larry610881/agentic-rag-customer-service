from abc import ABC, abstractmethod


class FileStorageService(ABC):
    @abstractmethod
    async def save_bot_icon(self, bot_id: str, content: bytes, ext: str) -> str:
        """Save bot icon file, return the URL path."""
        ...

    @abstractmethod
    async def delete_bot_icon(self, bot_id: str) -> None:
        """Delete bot icon file if exists."""
        ...
