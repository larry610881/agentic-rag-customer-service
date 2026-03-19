from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.observability.log_retention_policy import (
    LogRetentionPolicy,
    LogRetentionPolicyRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.log_retention_policy_model import (
    LogRetentionPolicyModel,
)
from src.infrastructure.db.models.request_log_model import RequestLogModel


class SQLAlchemyLogRetentionPolicyRepository(LogRetentionPolicyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: LogRetentionPolicyModel) -> LogRetentionPolicy:
        return LogRetentionPolicy(
            id=model.id,
            enabled=model.enabled,
            retention_days=model.retention_days,
            cleanup_hour=model.cleanup_hour,
            cleanup_interval_hours=model.cleanup_interval_hours,
            last_cleanup_at=model.last_cleanup_at,
            deleted_count_last=model.deleted_count_last,
            updated_at=model.updated_at,
        )

    async def get(self) -> LogRetentionPolicy | None:
        stmt = select(LogRetentionPolicyModel).where(
            LogRetentionPolicyModel.id == "system"
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            return self._to_entity(model)
        return None

    async def save(self, policy: LogRetentionPolicy) -> LogRetentionPolicy:
        async with atomic(self._session):
            existing = await self._session.get(LogRetentionPolicyModel, policy.id)
            if existing:
                existing.enabled = policy.enabled
                existing.retention_days = policy.retention_days
                existing.cleanup_hour = policy.cleanup_hour
                existing.cleanup_interval_hours = policy.cleanup_interval_hours
                existing.last_cleanup_at = policy.last_cleanup_at
                existing.deleted_count_last = policy.deleted_count_last
                existing.updated_at = datetime.now(timezone.utc)
            else:
                self._session.add(
                    LogRetentionPolicyModel(
                        id=policy.id,
                        enabled=policy.enabled,
                        retention_days=policy.retention_days,
                        cleanup_hour=policy.cleanup_hour,
                        cleanup_interval_hours=policy.cleanup_interval_hours,
                        last_cleanup_at=policy.last_cleanup_at,
                        deleted_count_last=policy.deleted_count_last,
                        updated_at=policy.updated_at,
                    )
                )
        return policy

    async def cleanup_logs_before(self, cutoff: datetime) -> int:
        count_stmt = (
            select(func.count())
            .select_from(RequestLogModel)
            .where(RequestLogModel.created_at < cutoff)
        )
        count = (await self._session.execute(count_stmt)).scalar() or 0
        if count > 0:
            async with atomic(self._session):
                del_stmt = delete(RequestLogModel).where(
                    RequestLogModel.created_at < cutoff
                )
                await self._session.execute(del_stmt)
        return count
