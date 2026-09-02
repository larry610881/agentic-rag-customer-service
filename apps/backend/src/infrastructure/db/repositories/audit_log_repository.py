from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.audit.entity import AuditEntry, AuditLogRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.audit_log_model import AuditLogModel


class SQLAlchemyAuditLogRepository(AuditLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: AuditEntry) -> None:
        async with atomic(self._session):
            self._session.add(AuditLogModel(
                id=entry.id,
                tenant_id=entry.tenant_id,
                actor_user_id=entry.actor_user_id,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                action=entry.action,
                changed_fields=entry.changed_fields,
                source=entry.source,
                created_at=entry.created_at,
            ))

    async def list_entries(
        self,
        *,
        tenant_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEntry]:
        stmt = select(AuditLogModel)
        if tenant_id is not None:
            stmt = stmt.where(AuditLogModel.tenant_id == tenant_id)
        if entity_type is not None:
            stmt = stmt.where(AuditLogModel.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditLogModel.entity_id == entity_id)
        stmt = (
            stmt.order_by(AuditLogModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            AuditEntry(
                id=r.id,
                tenant_id=r.tenant_id,
                actor_user_id=r.actor_user_id,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                action=r.action,
                changed_fields=r.changed_fields or {},
                source=r.source,
                created_at=r.created_at,
            )
            for r in rows
        ]
