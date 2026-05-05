"""Publish Outbox Event Use Case

CRITICAL：在業務 SQL 同 transaction 內 INSERT outbox row，atomic 保證。
caller 必須包在 ``async with atomic(session):`` 內：

    async with atomic(self._session):
        await self._publish_outbox.execute(event)  # INSERT outbox
        await self._kb_repo.delete(kb_id)           # 業務 SQL
    # commit 在 atomic 外做；commit 後 worker 才能看到 outbox row
"""
from __future__ import annotations

import structlog

from src.domain.outbox.entity import OutboxEvent
from src.domain.outbox.repository import OutboxEventRepository

logger = structlog.get_logger(__name__)


class PublishOutboxEventUseCase:
    """把 OutboxEvent 寫進 outbox_events 表（不 commit，由 atomic() 統一控制）。"""

    def __init__(self, outbox_repo: OutboxEventRepository) -> None:
        self._outbox_repo = outbox_repo

    async def execute(self, event: OutboxEvent) -> None:
        await self._outbox_repo.save(event)
        logger.info(
            "outbox.event.published",
            event_id=event.id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            tenant_id=event.tenant_id,
        )
