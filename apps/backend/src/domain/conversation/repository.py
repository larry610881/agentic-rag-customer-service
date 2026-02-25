"""Conversation Repository 介面"""

from abc import ABC, abstractmethod

from src.domain.conversation.entity import Conversation


class ConversationRepository(ABC):
    @abstractmethod
    async def save(self, conversation: Conversation) -> None: ...

    @abstractmethod
    async def find_by_id(self, conversation_id: str) -> Conversation | None: ...

    @abstractmethod
    async def find_by_tenant(
        self, tenant_id: str, *, bot_id: str | None = None
    ) -> list[Conversation]: ...
