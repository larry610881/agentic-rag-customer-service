from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.abuse.settings import (
    SCOPE_PROFILE,
    AbuseSettings,
    AbuseSettingsRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.abuse_settings_model import AbuseSettingsModel


class SQLAlchemyAbuseSettingsRepository(AbuseSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: AbuseSettingsModel) -> AbuseSettings:
        return AbuseSettings(
            id=m.id,
            scope_kind=m.scope_kind,
            scope_id=m.scope_id,
            overrides=dict(m.overrides or {}),
            updated_by=m.updated_by,
            updated_at=m.updated_at,
        )

    async def get(self, scope_kind: str, scope_id: str) -> AbuseSettings | None:
        stmt = select(AbuseSettingsModel).where(
            AbuseSettingsModel.scope_kind == scope_kind,
            AbuseSettingsModel.scope_id == scope_id,
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(m) if m is not None else None

    async def save(self, settings: AbuseSettings) -> None:
        async with atomic(self._session):
            stmt = select(AbuseSettingsModel).where(
                AbuseSettingsModel.scope_kind == settings.scope_kind,
                AbuseSettingsModel.scope_id == settings.scope_id,
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                existing.overrides = dict(settings.overrides)
                existing.updated_by = settings.updated_by
                existing.updated_at = settings.updated_at
                return
            self._session.add(AbuseSettingsModel(
                id=settings.id,
                scope_kind=settings.scope_kind,
                scope_id=settings.scope_id,
                overrides=dict(settings.overrides),
                updated_by=settings.updated_by,
                updated_at=settings.updated_at,
            ))

    async def list_profiles(self) -> list[AbuseSettings]:
        stmt = (
            select(AbuseSettingsModel)
            .where(AbuseSettingsModel.scope_kind == SCOPE_PROFILE)
            .order_by(AbuseSettingsModel.scope_id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in rows]
