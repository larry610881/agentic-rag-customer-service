"""LINE Messaging 服務介面"""

from abc import ABC, abstractmethod


class LineMessagingService(ABC):
    @abstractmethod
    async def reply_text(self, reply_token: str, text: str) -> None: ...

    @abstractmethod
    async def reply_with_quick_reply(
        self, reply_token: str, text: str, message_id: str,
        extra_messages: list[dict] | None = None,
    ) -> None: ...

    @abstractmethod
    async def reply_with_reason_options(
        self, reply_token: str, message_id: str
    ) -> None: ...

    @abstractmethod
    async def push_with_quick_reply(
        self, user_id: str, text: str, message_id: str
    ) -> None: ...

    @abstractmethod
    async def push_flex(
        self, user_id: str, alt_text: str, flex_content: dict
    ) -> None: ...

    @abstractmethod
    async def show_loading(self, user_id: str, seconds: int = 20) -> None: ...

    @abstractmethod
    async def verify_signature(self, body: str, signature: str) -> bool: ...


class LineMessagingServiceFactory(ABC):
    @abstractmethod
    def create(
        self, channel_secret: str, channel_access_token: str
    ) -> LineMessagingService: ...


class WebhookEventDeduplicator(ABC):
    """Issue #58：以 webhookEventId 認領事件，redelivery 重送時不重複處理。"""

    @abstractmethod
    async def claim(self, event_id: str) -> bool:
        """第一次認領回 True；已處理過回 False。實作在 Redis 不可用時應 fail-open。"""
