"""Fire-and-forget notification dispatch helper."""

import redis.asyncio as aioredis
import structlog

from src.application.observability.config_change_notification_use_case import (
    DispatchConfigChangeNotificationUseCase,
)
from src.application.observability.notification_use_cases import (
    DispatchAbuseNotificationUseCase,
    DispatchDiagnosticNotificationUseCase,
    DispatchNotificationUseCase,
    NotificationDispatcher,
)
from src.config import Settings
from src.domain.abuse.events import AbuseAlertEvent
from src.domain.audit.entity import AuditEntry
from src.domain.observability.config_change import NOTIFIABLE_ENTITY_TYPES
from src.domain.observability.diagnostic import DiagnosticEvent
from src.domain.observability.error_event import ErrorEvent
from src.infrastructure.crypto.aes_encryption_service import AESEncryptionService
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.repositories.bot_repository import SQLAlchemyBotRepository
from src.infrastructure.db.repositories.notification_channel_repository import (
    SQLAlchemyNotificationChannelRepository,
)
from src.infrastructure.db.repositories.tenant_repository import (
    SQLAlchemyTenantRepository,
)
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.db.repositories.worker_config_repository import (
    SQLAlchemyWorkerConfigRepository,
)
from src.infrastructure.notification.email_sender import EmailNotificationSender
from src.infrastructure.notification.redis_throttle import RedisNotificationThrottle
from src.infrastructure.notification.teams_workflow_sender import TeamsWorkflowSender

_logger = structlog.get_logger("dispatch_helper")


def _build_dispatcher(settings: Settings) -> NotificationDispatcher:
    senders: dict = {
        "email": EmailNotificationSender(),
        "teams": TeamsWorkflowSender(),
    }
    return NotificationDispatcher(
        senders=senders,
        encryption_service=AESEncryptionService(
            master_key=settings.encryption_master_key or "0" * 64
        ),
    )


def _build_infra():
    """Shared infrastructure setup for fire-and-forget dispatchers."""
    settings = Settings()
    redis = aioredis.Redis.from_url(settings.redis_url, decode_responses=False)
    throttle = RedisNotificationThrottle(redis)
    return redis, throttle, _build_dispatcher(settings)


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


async def dispatch_config_change_notification(entry: AuditEntry) -> None:
    """Fire-and-forget（Issue #77）：稽核列成功寫入後的設定變更通知。

    掛在 ``AuditRecorder.on_recorded``；非租戶 scope 或非 bot / worker / 防護的稽核列
    在建任何連線前就略過。不節流：設定變更是離散事件，每筆都該通知。
    """
    if not entry.tenant_id or entry.entity_type not in NOTIFIABLE_ENTITY_TYPES:
        return
    try:
        dispatcher = _build_dispatcher(Settings())
        async with async_session_factory() as session:
            uc = DispatchConfigChangeNotificationUseCase(
                channel_repo=SQLAlchemyNotificationChannelRepository(session),
                tenant_repository=SQLAlchemyTenantRepository(session),
                dispatcher=dispatcher,
                user_repository=SQLAlchemyUserRepository(session),
                bot_repository=SQLAlchemyBotRepository(session),
                worker_repository=SQLAlchemyWorkerConfigRepository(session),
            )
            await uc.execute(entry)
    except Exception:
        _logger.warning(
            "notification.config_change_fire_and_forget_failed", exc_info=True
        )
