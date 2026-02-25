"""Feedback Repository 介面"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.conversation.feedback_analysis_vo import (
    DailyFeedbackStat,
    RetrievalQualityRecord,
    TagCount,
)
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

    @abstractmethod
    async def update_tags(
        self, message_id: str, tags: list[str]
    ) -> None: ...

    @abstractmethod
    async def get_daily_trend(
        self, tenant_id: str, days: int = 30
    ) -> list[DailyFeedbackStat]: ...

    @abstractmethod
    async def get_top_tags(
        self, tenant_id: str, days: int = 30, limit: int = 10
    ) -> list[TagCount]: ...

    @abstractmethod
    async def get_negative_with_context(
        self, tenant_id: str, days: int = 30, limit: int = 20
    ) -> list[RetrievalQualityRecord]: ...

    @abstractmethod
    async def find_by_date_range(
        self, tenant_id: str, start: datetime, end: datetime
    ) -> list[Feedback]: ...

    @abstractmethod
    async def delete_before_date(
        self, tenant_id: str, before: datetime
    ) -> int: ...
