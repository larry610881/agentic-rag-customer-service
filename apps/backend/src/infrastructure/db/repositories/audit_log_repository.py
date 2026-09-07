from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.audit.entity import (
    AuditEntry,
    AuditLogRepository,
    decode_audit_cursor,
)
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
                parent_entity_type=entry.parent_entity_type,
                parent_entity_id=entry.parent_entity_id,
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
        return [self._to_entity(r) for r in rows]

    async def find_by_entity(
        self,
        *,
        entity_type: str,
        entity_id: str,
        limit: int,
        cursor: str | None = None,
    ) -> list[AuditEntry]:
        stmt = select(AuditLogModel).where(
            AuditLogModel.entity_type == entity_type,
            AuditLogModel.entity_id == entity_id,
        )
        return await self._keyset_page(stmt, limit, cursor)

    async def find_by_entity_or_parent(
        self,
        *,
        entity_type: str,
        entity_id: str,
        parent_entity_type: str,
        parent_entity_id: str,
        limit: int,
        cursor: str | None = None,
    ) -> list[AuditEntry]:
        """Issue #77：實體本身 ∪ 以它為 parent 的列（bot ∪ 其 worker），
        單一 keyset 查詢。"""
        stmt = select(AuditLogModel).where(
            or_(
                and_(
                    AuditLogModel.entity_type == entity_type,
                    AuditLogModel.entity_id == entity_id,
                ),
                and_(
                    AuditLogModel.parent_entity_type == parent_entity_type,
                    AuditLogModel.parent_entity_id == parent_entity_id,
                ),
            )
        )
        return await self._keyset_page(stmt, limit, cursor)

    async def _keyset_page(
        self, stmt: Select[tuple[AuditLogModel]], limit: int, cursor: str | None
    ) -> list[AuditEntry]:
        """新→舊（created_at desc, id desc）；cursor 之後只取更舊的列。"""
        if cursor is not None:
            ts, last_id = decode_audit_cursor(cursor)
            stmt = stmt.where(
                or_(
                    AuditLogModel.created_at < ts,
                    and_(
                        AuditLogModel.created_at == ts,
                        AuditLogModel.id < last_id,
                    ),
                )
            )
        stmt = (
            stmt.order_by(AuditLogModel.created_at.desc(), AuditLogModel.id.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(r) for r in rows]

    @staticmethod
    def _to_entity(r: AuditLogModel) -> AuditEntry:
        return AuditEntry(
            id=r.id,
            tenant_id=r.tenant_id,
            actor_user_id=r.actor_user_id,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            action=r.action,
            changed_fields=r.changed_fields or {},
            source=r.source,
            created_at=r.created_at,
            parent_entity_type=r.parent_entity_type,
            parent_entity_id=r.parent_entity_id,
        )
