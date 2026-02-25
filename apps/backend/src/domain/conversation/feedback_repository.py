"""Feedback Repository 介面"""

from abc import ABC, abstractmethod

from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_value_objects import Rating


class FeedbackRepository(ABC):
    @abstractmethod
    async def save(self, feedback: Feedback) -> None: ...

    @abstractmethod
    async def find_by_message_id(self, message_id: str) -> Feedback | None: ...

    @abstractmethod
    async def find_by_tenant(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[Feedback]: ...

    @abstractmethod
    async def find_by_conversation(
        self, conversation_id: str
    ) -> list[Feedback]: ...

    @abstractmethod
    async def count_by_tenant_and_rating(
        self, tenant_id: str, rating: Rating | None = None
    ) -> int: ...
