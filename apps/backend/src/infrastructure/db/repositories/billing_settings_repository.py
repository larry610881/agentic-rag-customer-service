"""SQLAlchemy BillingSettings Repository — Issue #74（單列 upsert）"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.billing.settings import (
    BILLING_SETTINGS_ID,
    BillingSettings,
    BillingSettingsRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.billing_settings_model import BillingSettingsModel


class SQLAlchemyBillingSettingsRepository(BillingSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> BillingSettings | None:
        m = await self._session.get(BillingSettingsModel, BILLING_SETTINGS_ID)
        if m is None:
            return None
        return BillingSettings(
            id=m.id,
            usd_per_point=Decimal(m.usd_per_point),
            updated_by=m.updated_by,
            updated_at=m.updated_at,
        )

    async def save(self, settings: BillingSettings) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                BillingSettingsModel, BILLING_SETTINGS_ID
            )
            if existing is not None:
                existing.usd_per_point = settings.usd_per_point
                existing.updated_by = settings.updated_by
                existing.updated_at = settings.updated_at
                return
            self._session.add(
                BillingSettingsModel(
                    id=BILLING_SETTINGS_ID,
                    usd_per_point=settings.usd_per_point,
                    updated_by=settings.updated_by,
                    updated_at=settings.updated_at,
                )
            )
