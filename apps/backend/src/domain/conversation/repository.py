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

    @abstractmethod
    async def find_pending_summary(
        self,
        *,
        idle_minutes: int = 5,
        limit: int = 200,
    ) -> list[str]:
        """S-Gov.6b: 找需要生 summary 的 conversation_id。

        條件：閒置 idle_minutes 分鐘 + (從未生 OR 對話有變化)
            WHERE last_message_at < NOW() - INTERVAL 'idle_minutes minutes'
              AND (summary IS NULL OR summary_message_count < message_count)
        """
        ...

    @abstractmethod
    async def search_summary_by_keyword(
        self,
        *,
        keyword: str,
        tenant_id: str | None = None,
        bot_id: str | None = None,
        limit: int = 20,
    ) -> list[Conversation]:
        """S-Gov.6b: PG ILIKE 搜尋 summary 欄位（不載入 messages）。"""
        ...

    @abstractmethod
    async def find_by_ids(
        self, conversation_ids: list[str]
    ) -> list[Conversation]:
        """S-Gov.6b: 批次取 conversation header（給 semantic search hydrate 用，不載 messages）。"""
        ...
