"""SQLAlchemy QuotaAlertLog Repository — S-Token-Gov.3

冪等性策略：save_if_new 嘗試 INSERT，若 UNIQUE(tenant_id, cycle, alert_type)
違反 → 回 None。cron 重跑同 alert 不會重複寫，DB 層直接擋。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.billing.quota_alert import (
    QuotaAlertLog,
    QuotaAlertLogRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.quota_alert_log_model import (
    QuotaAlertLogModel,
)


class SQLAlchemyQuotaAlertLogRepository(QuotaAlertLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, m: QuotaAlertLogModel) -> QuotaAlertLog:
        return QuotaAlertLog(
            id=m.id,
            tenant_id=m.tenant_id,
            cycle_year_month=m.cycle_year_month,
            alert_type=m.alert_type,
            used_ratio=m.used_ratio,
            message=m.message or "",
            delivered_to_email=m.delivered_to_email,
            created_at=m.created_at,
        )

    async def save_if_new(
        self, alert: QuotaAlertLog
    ) -> QuotaAlertLog | None:
        try:
            async with atomic(self._session):
                model = QuotaAlertLogModel(
                    id=alert.id,
                    tenant_id=alert.tenant_id,
                    cycle_year_month=alert.cycle_year_month,
                    alert_type=alert.alert_type,
                    used_ratio=alert.used_ratio,
                    message=alert.message or None,
                    delivered_to_email=alert.delivered_to_email,
                    created_at=alert.created_at,
                )
                self._session.add(model)
            return alert
        except IntegrityError:
            # UNIQUE 違反 — 該 cycle 該 alert_type 已存在
            await self._session.rollback()
            return None

    async def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[QuotaAlertLog]:
        stmt = select(QuotaAlertLogModel).order_by(
            QuotaAlertLogModel.created_at.desc()
        )
        if tenant_id is not None:
            stmt = stmt.where(QuotaAlertLogModel.tenant_id == tenant_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_recent(
        self, tenant_id: str | None = None
    ) -> int:
        stmt = select(func.count()).select_from(QuotaAlertLogModel)
        if tenant_id is not None:
            stmt = stmt.where(QuotaAlertLogModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    async def find_by_tenant_and_cycle(
        self, tenant_id: str, cycle: str
    ) -> list[QuotaAlertLog]:
        stmt = (
            select(QuotaAlertLogModel)
            .where(
                QuotaAlertLogModel.tenant_id == tenant_id,
                QuotaAlertLogModel.cycle_year_month == cycle,
            )
            .order_by(QuotaAlertLogModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    # --- S-Token-Gov.3.5: Email dispatch ---

    async def find_undelivered(
        self, *, limit: int = 100
    ) -> list[QuotaAlertLog]:
        stmt = (
            select(QuotaAlertLogModel)
            .where(QuotaAlertLogModel.delivered_to_email.is_(False))
            .order_by(QuotaAlertLogModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def mark_delivered(self, alert_id: str) -> None:
        async with atomic(self._session):
            existing = await self._session.get(QuotaAlertLogModel, alert_id)
            if existing is not None:
                existing.delivered_to_email = True
