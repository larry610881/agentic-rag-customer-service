"""Fire-and-forget notification dispatch helper."""

import redis.asyncio as aioredis
import structlog

from src.application.observability.notification_use_cases import (
    DispatchNotificationUseCase,
    NotificationDispatcher,
)
from src.config import Settings
from src.domain.observability.error_event import ErrorEvent
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.repositories.notification_channel_repository import (
    SQLAlchemyNotificationChannelRepository,
)
from src.infrastructure.notification.email_sender import EmailNotificationSender
from src.infrastructure.notification.redis_throttle import RedisNotificationThrottle

_logger = structlog.get_logger("dispatch_helper")


async def dispatch_error_notification(event: ErrorEvent) -> None:
    """Fire-and-forget: load channels, check Redis throttle, send notifications."""
    try:
        settings = Settings()
        redis = aioredis.Redis.from_url(settings.redis_url, decode_responses=False)
        throttle = RedisNotificationThrottle(redis)
        senders: dict = {"email": EmailNotificationSender()}
        dispatcher = NotificationDispatcher(senders=senders)

        async with async_session_factory() as session:
            channel_repo = SQLAlchemyNotificationChannelRepository(session)
            uc = DispatchNotificationUseCase(
                channel_repo=channel_repo,
                throttle_service=throttle,
                dispatcher=dispatcher,
            )
            await uc.execute(event)
        await redis.aclose()
    except Exception:
        _logger.warning("notification.fire_and_forget_failed", exc_info=True)
