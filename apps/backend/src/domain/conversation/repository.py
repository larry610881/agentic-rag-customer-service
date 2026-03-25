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
        self,
        tenant_id: str,
        *,
        bot_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Conversation]: ...

    @abstractmethod
    async def count_by_tenant(
        self, tenant_id: str, *, bot_id: str | None = None
    ) -> int: ...

    @abstractmethod
    async def find_latest_by_visitor(
        self, visitor_id: str, bot_id: str
    ) -> Conversation | None:
        """Find the most recent conversation for an external user (e.g. LINE user_id)."""
        ...

    @abstractmethod
    async def find_conversation_id_by_message(
        self, message_id: str
    ) -> str | None:
        """Look up which conversation a message belongs to."""
        ...
