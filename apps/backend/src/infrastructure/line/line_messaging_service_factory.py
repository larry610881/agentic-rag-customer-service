"""LINE Messaging Service Factory 實作"""

from src.domain.line.services import LineMessagingService, LineMessagingServiceFactory
from src.infrastructure.line.line_messaging_service import HttpxLineMessagingService


class HttpxLineMessagingServiceFactory(LineMessagingServiceFactory):
    def create(
        self, channel_secret: str, channel_access_token: str
    ) -> LineMessagingService:
        return HttpxLineMessagingService(channel_secret, channel_access_token)
