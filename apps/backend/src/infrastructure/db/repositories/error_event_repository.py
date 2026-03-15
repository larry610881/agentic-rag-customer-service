"""SQLAlchemy implementation of ErrorEventRepository."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.observability.error_event import ErrorEvent, ErrorEventRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.error_event_model import ErrorEventModel
from src.infrastructure.db.models.error_notification_log_model import (
    ErrorNotificationLogModel,
)


class SQLAlchemyErrorEventRepository(ErrorEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: ErrorEventModel) -> ErrorEvent:
        return ErrorEvent(
            id=m.id,
            fingerprint=m.fingerprint,
            source=m.source,
            error_type=m.error_type,
            message=m.message,
            stack_trace=m.stack_trace,
            request_id=m.request_id,
            path=m.path,
            method=m.method,
            status_code=m.status_code,
            tenant_id=m.tenant_id,
            user_agent=m.user_agent,
            extra=m.extra,
            resolved=m.resolved,
            resolved_at=m.resolved_at,
            resolved_by=m.resolved_by,
            created_at=m.created_at,
        )

    async def save(self, event: ErrorEvent) -> ErrorEvent:
        async with atomic(self._session):
            self._session.add(
                ErrorEventModel(
                    id=event.id,
                    fingerprint=event.fingerprint,
                    source=event.source,
                    error_type=event.error_type,
                    message=event.message,
                    stack_trace=event.stack_trace,
                    request_id=event.request_id,
                    path=event.path,
                    method=event.method,
                    status_code=event.status_code,
                    tenant_id=event.tenant_id,
                    user_agent=event.user_agent,
                    extra=event.extra,
                    resolved=event.resolved,
                    resolved_at=event.resolved_at,
                    resolved_by=event.resolved_by,
                    created_at=event.created_at,
                )
            )
        return event

    async def get_by_id(self, event_id: str) -> ErrorEvent | None:
        stmt = select(ErrorEventModel).where(ErrorEventModel.id == event_id)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def list_events(
        self,
        *,
        source: str | None = None,
        resolved: bool | None = None,
        fingerprint: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ErrorEvent], int]:
        stmt = select(ErrorEventModel).order_by(
            ErrorEventModel.created_at.desc()
        )
        count_stmt = select(func.count()).select_from(ErrorEventModel)

        if source is not None:
            stmt = stmt.where(ErrorEventModel.source == source)
            count_stmt = count_stmt.where(ErrorEventModel.source == source)
        if resolved is not None:
            stmt = stmt.where(ErrorEventModel.resolved == resolved)
            count_stmt = count_stmt.where(
                ErrorEventModel.resolved == resolved
            )
        if fingerprint is not None:
            stmt = stmt.where(ErrorEventModel.fingerprint == fingerprint)
            count_stmt = count_stmt.where(
                ErrorEventModel.fingerprint == fingerprint
            )
        if tenant_id is not None:
            stmt = stmt.where(ErrorEventModel.tenant_id == tenant_id)
            count_stmt = count_stmt.where(
                ErrorEventModel.tenant_id == tenant_id
            )

        total = (await self._session.execute(count_stmt)).scalar() or 0
        rows = (
            (await self._session.execute(stmt.offset(offset).limit(limit)))
            .scalars()
            .all()
        )
        return [self._to_entity(r) for r in rows], total

    async def resolve(
        self, event_id: str, resolved_by: str
    ) -> ErrorEvent | None:
        async with atomic(self._session):
            m = await self._session.get(ErrorEventModel, event_id)
            if m is None:
                return None
            m.resolved = True
            m.resolved_at = datetime.now(timezone.utc)
            m.resolved_by = resolved_by
        return self._to_entity(m)

    async def count_by_fingerprint(self, fingerprint: str) -> int:
        stmt = (
            select(func.count())
            .select_from(ErrorEventModel)
            .where(ErrorEventModel.fingerprint == fingerprint)
        )
        return (await self._session.execute(stmt)).scalar() or 0

    async def last_notified_at(
        self, fingerprint: str, channel_id: str
    ) -> datetime | None:
        stmt = (
            select(ErrorNotificationLogModel.created_at)
            .where(ErrorNotificationLogModel.fingerprint == fingerprint)
            .where(ErrorNotificationLogModel.channel_id == channel_id)
            .order_by(ErrorNotificationLogModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    async def record_notification(
        self, fingerprint: str, channel_id: str
    ) -> None:
        async with atomic(self._session):
            self._session.add(
                ErrorNotificationLogModel(
                    id=uuid.uuid4().hex,
                    fingerprint=fingerprint,
                    channel_id=channel_id,
                    created_at=datetime.now(timezone.utc),
                )
            )

    async def cleanup_before(self, cutoff: datetime) -> int:
        count_stmt = (
            select(func.count())
            .select_from(ErrorEventModel)
            .where(ErrorEventModel.created_at < cutoff)
        )
        count = (await self._session.execute(count_stmt)).scalar() or 0
        if count > 0:
            async with atomic(self._session):
                await self._session.execute(
                    delete(ErrorEventModel).where(
                        ErrorEventModel.created_at < cutoff
                    )
                )
        return count
