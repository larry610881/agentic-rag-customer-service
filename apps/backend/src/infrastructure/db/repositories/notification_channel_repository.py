"""SQLAlchemy implementation of NotificationChannelRepository."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.observability.notification import (
    NotificationChannel,
    NotificationChannelRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.notification_channel_model import (
    NotificationChannelModel,
)


class SQLAlchemyNotificationChannelRepository(NotificationChannelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: NotificationChannelModel) -> NotificationChannel:
        return NotificationChannel(
            id=m.id,
            channel_type=m.channel_type,
            name=m.name,
            enabled=m.enabled,
            config_encrypted=m.config_encrypted,
            throttle_minutes=m.throttle_minutes,
            min_severity=m.min_severity,
            notify_diagnostics=m.notify_diagnostics,
            diagnostic_severity=m.diagnostic_severity,
            updated_at=m.updated_at,
            created_at=m.created_at,
        )

    async def save(
        self, channel: NotificationChannel
    ) -> NotificationChannel:
        async with atomic(self._session):
            existing = await self._session.get(
                NotificationChannelModel, channel.id
            )
            if existing:
                existing.channel_type = channel.channel_type
                existing.name = channel.name
                existing.enabled = channel.enabled
                existing.config_encrypted = channel.config_encrypted
                existing.throttle_minutes = channel.throttle_minutes
                existing.min_severity = channel.min_severity
                existing.notify_diagnostics = channel.notify_diagnostics
                existing.diagnostic_severity = channel.diagnostic_severity
                existing.updated_at = datetime.now(timezone.utc)
            else:
                self._session.add(
                    NotificationChannelModel(
                        id=channel.id,
                        channel_type=channel.channel_type,
                        name=channel.name,
                        enabled=channel.enabled,
                        config_encrypted=channel.config_encrypted,
                        throttle_minutes=channel.throttle_minutes,
                        min_severity=channel.min_severity,
                        notify_diagnostics=channel.notify_diagnostics,
                        diagnostic_severity=channel.diagnostic_severity,
                        updated_at=channel.updated_at,
                        created_at=channel.created_at,
                    )
                )
        return channel

    async def get_by_id(
        self, channel_id: str
    ) -> NotificationChannel | None:
        stmt = select(NotificationChannelModel).where(
            NotificationChannelModel.id == channel_id
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def list_all(self) -> list[NotificationChannel]:
        stmt = select(NotificationChannelModel).order_by(
            NotificationChannelModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_enabled(self) -> list[NotificationChannel]:
        stmt = (
            select(NotificationChannelModel)
            .where(NotificationChannelModel.enabled.is_(True))
            .order_by(NotificationChannelModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, channel_id: str) -> bool:
        async with atomic(self._session):
            result = await self._session.execute(
                delete(NotificationChannelModel).where(
                    NotificationChannelModel.id == channel_id
                )
            )
        return result.rowcount > 0
