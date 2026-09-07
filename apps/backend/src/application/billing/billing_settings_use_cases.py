"""平台計價設定用例（僅 system_admin）— Issue #74"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.domain.billing.settings import BillingSettings, BillingSettingsRepository
from src.domain.shared.exceptions import ValidationError

AUDIT_ENTITY = "billing_settings"


class GetBillingSettingsUseCase:
    def __init__(self, repo: BillingSettingsRepository) -> None:
        self._repo = repo

    async def execute(self) -> BillingSettings:
        return await self._repo.get() or BillingSettings()


class UpdateBillingSettingsUseCase:
    def __init__(
        self,
        repo: BillingSettingsRepository,
        billing_context: Any | None = None,
        audit: Any | None = None,
    ) -> None:
        self._repo = repo
        self._billing_context = billing_context
        self._audit = audit

    async def execute(
        self, *, usd_per_point: Decimal, actor_user_id: str | None
    ) -> BillingSettings:
        if usd_per_point <= 0:
            raise ValidationError("usd_per_point must be > 0")
        existing = await self._repo.get()
        before = {"usd_per_point": str(existing.usd_per_point)} if existing else {}
        settings = BillingSettings(
            usd_per_point=Decimal(usd_per_point),
            updated_by=actor_user_id,
            updated_at=datetime.now(timezone.utc),
        )
        await self._repo.save(settings)
        if self._billing_context is not None:
            self._billing_context.invalidate(None)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=settings.id,
                action="update",
                before=before,
                after={"usd_per_point": str(settings.usd_per_point)},
                actor_user_id=actor_user_id,
            )
        return settings
