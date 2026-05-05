"""SQLAlchemy Outbox Event Repository.

claim_batch 用 SELECT FOR UPDATE SKIP LOCKED — PostgreSQL 原生 lease pattern：
- 多 worker 同時跑時各自撈不同 row 不互相阻塞
- 同一 row 不會被兩個 worker 同時撈
- crash 的 worker 留下 lease 由下一輪 batch 透過 ``locked_at`` timeout 回收
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.outbox.entity import OutboxEvent, OutboxEventStatus
from src.domain.outbox.repository import OutboxEventRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.outbox_event_model import OutboxEventModel


class SQLAlchemyOutboxEventRepository(OutboxEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: OutboxEventModel) -> OutboxEvent:
        return OutboxEvent(
            id=m.id,
            tenant_id=m.tenant_id,
            aggregate_type=m.aggregate_type,
            aggregate_id=m.aggregate_id,
            event_type=m.event_type,
            payload=dict(m.payload or {}),
            doc_watermark_ts=m.doc_watermark_ts,
            status=m.status,
            attempts=m.attempts,
            max_attempts=m.max_attempts,
            next_attempt_at=m.next_attempt_at,
            last_error=m.last_error,
            locked_by=m.locked_by,
            locked_at=m.locked_at,
            created_at=m.created_at,
            completed_at=m.completed_at,
        )

    async def save(self, event: OutboxEvent) -> None:
        """INSERT 新事件（不 commit — 由 caller 透過 atomic() 控制）。"""
        row = OutboxEventModel(
            id=event.id,
            tenant_id=event.tenant_id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            payload=event.payload,
            doc_watermark_ts=event.doc_watermark_ts,
            status=event.status,
            attempts=event.attempts,
            max_attempts=event.max_attempts,
            next_attempt_at=event.next_attempt_at,
            last_error=event.last_error,
            locked_by=event.locked_by,
            locked_at=event.locked_at,
            created_at=event.created_at,
            completed_at=event.completed_at,
        )
        self._session.add(row)
        # 不 flush 也不 commit — atomic() 統一管理

    async def claim_batch(
        self,
        worker_id: str,
        batch_size: int = 50,
        lease_timeout_seconds: int = 300,
    ) -> list[OutboxEvent]:
        """撈 batch 並 set lease（同一 transaction 內 SELECT FOR UPDATE + UPDATE）。

        撈取條件（OR 兩條）：
        1. status='pending' AND next_attempt_at <= NOW()
        2. status='in_progress' AND locked_at < NOW() - lease_timeout（lease 過期回收）
        """
        now = datetime.now(timezone.utc)
        lease_deadline = now - timedelta(seconds=lease_timeout_seconds)

        async with atomic(self._session):
            stmt = (
                select(OutboxEventModel)
                .where(
                    or_(
                        (OutboxEventModel.status == OutboxEventStatus.PENDING.value)
                        & (OutboxEventModel.next_attempt_at <= now),
                        (
                            OutboxEventModel.status
                            == OutboxEventStatus.IN_PROGRESS.value
                        )
                        & (OutboxEventModel.locked_at < lease_deadline),
                    )
                )
                .order_by(OutboxEventModel.next_attempt_at.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            result = await self._session.execute(stmt)
            rows = list(result.scalars().all())

            if not rows:
                return []

            ids = [r.id for r in rows]
            await self._session.execute(
                update(OutboxEventModel)
                .where(OutboxEventModel.id.in_(ids))
                .values(
                    status=OutboxEventStatus.IN_PROGRESS.value,
                    locked_by=worker_id,
                    locked_at=now,
                )
            )

        # commit 之後再讀一次 entity（lock 已釋放）
        events: list[OutboxEvent] = []
        for r in rows:
            r.status = OutboxEventStatus.IN_PROGRESS.value
            r.locked_by = worker_id
            r.locked_at = now
            events.append(self._to_entity(r))
        return events

    async def update(self, event: OutboxEvent) -> None:
        """更新事件狀態（done / failed / dead 後的單筆更新，自帶 commit）。"""
        async with atomic(self._session):
            await self._session.execute(
                update(OutboxEventModel)
                .where(OutboxEventModel.id == event.id)
                .values(
                    status=event.status,
                    attempts=event.attempts,
                    next_attempt_at=event.next_attempt_at,
                    last_error=event.last_error,
                    locked_by=event.locked_by,
                    locked_at=event.locked_at,
                    completed_at=event.completed_at,
                )
            )

    async def find_by_id(self, event_id: str) -> OutboxEvent | None:
        result = await self._session.execute(
            select(OutboxEventModel).where(OutboxEventModel.id == event_id)
        )
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def list_dead_letter(
        self,
        *,
        event_type: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OutboxEvent]:
        stmt = select(OutboxEventModel).where(
            OutboxEventModel.status == OutboxEventStatus.DEAD.value
        )
        if event_type:
            stmt = stmt.where(OutboxEventModel.event_type == event_type)
        if tenant_id:
            stmt = stmt.where(OutboxEventModel.tenant_id == tenant_id)
        stmt = (
            stmt.order_by(OutboxEventModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_status(self, status: str) -> int:
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(OutboxEventModel.id)).where(
                OutboxEventModel.status == status
            )
        )
        return int(result.scalar_one() or 0)
