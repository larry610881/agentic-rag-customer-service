"""LINE Messaging 服務介面"""

from abc import ABC, abstractmethod


class LineMessagingService(ABC):
    @abstractmethod
    async def reply_text(self, reply_token: str, text: str) -> None: ...

    @abstractmethod
    async def verify_signature(self, body: str, signature: str) -> bool: ...


class LineMessagingServiceFactory(ABC):
    @abstractmethod
    def create(
        self, channel_secret: str, channel_access_token: str
    ) -> LineMessagingService: ...
