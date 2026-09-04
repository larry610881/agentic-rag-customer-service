"""Fire-and-forget notification dispatch helper."""

import redis.asyncio as aioredis
import structlog

from src.application.observability.notification_use_cases import (
    DispatchAbuseNotificationUseCase,
    DispatchDiagnosticNotificationUseCase,
    DispatchNotificationUseCase,
    NotificationDispatcher,
)
from src.config import Settings
from src.domain.abuse.events import AbuseAlertEvent
from src.domain.observability.diagnostic import DiagnosticEvent
from src.domain.observability.error_event import ErrorEvent
from src.infrastructure.crypto.aes_encryption_service import AESEncryptionService
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.repositories.notification_channel_repository import (
    SQLAlchemyNotificationChannelRepository,
)
from src.infrastructure.notification.email_sender import EmailNotificationSender
from src.infrastructure.notification.redis_throttle import RedisNotificationThrottle
from src.infrastructure.notification.teams_workflow_sender import TeamsWorkflowSender

_logger = structlog.get_logger("dispatch_helper")


def _build_infra():
    """Shared infrastructure setup for fire-and-forget dispatchers."""
    settings = Settings()
    redis = aioredis.Redis.from_url(settings.redis_url, decode_responses=False)
    throttle = RedisNotificationThrottle(redis)
    senders: dict = {
        "email": EmailNotificationSender(),
        "teams": TeamsWorkflowSender(),
    }
    dispatcher = NotificationDispatcher(
        senders=senders,
        encryption_service=AESEncryptionService(
            master_key=settings.encryption_master_key or "0" * 64
        ),
    )
    return redis, throttle, dispatcher


async def dispatch_error_notification(event: ErrorEvent) -> None:
    """Fire-and-forget: load channels, check Redis throttle, send notifications."""
    try:
        redis, throttle, dispatcher = _build_infra()

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


async def dispatch_diagnostic_notification(event: DiagnosticEvent) -> None:
    """Fire-and-forget: dispatch diagnostic quality alerts to subscribed channels."""
    try:
        redis, throttle, dispatcher = _build_infra()

        async with async_session_factory() as session:
            channel_repo = SQLAlchemyNotificationChannelRepository(session)
            uc = DispatchDiagnosticNotificationUseCase(
                channel_repo=channel_repo,
                throttle_service=throttle,
                dispatcher=dispatcher,
            )
            await uc.execute(event)
        await redis.aclose()
    except Exception:
        _logger.warning(
            "notification.diagnostic_fire_and_forget_failed", exc_info=True
        )


async def dispatch_abuse_notification(event: AbuseAlertEvent) -> None:
    """Fire-and-forget（Issue #68 P7c）：異常控管告警 / 摘要。"""
    try:
        redis, throttle, dispatcher = _build_infra()

        async with async_session_factory() as session:
            channel_repo = SQLAlchemyNotificationChannelRepository(session)
            uc = DispatchAbuseNotificationUseCase(
                channel_repo=channel_repo,
                throttle_service=throttle,
                dispatcher=dispatcher,
            )
            await uc.execute(event)
        await redis.aclose()
    except Exception:
        _logger.warning("notification.abuse_fire_and_forget_failed", exc_info=True)
