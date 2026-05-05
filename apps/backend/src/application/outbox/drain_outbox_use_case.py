"""Drain Outbox Use Case — Worker 端週期執行

每次 cron tick 撈 batch（含過期 lease 回收）→ 對每筆 dispatch handler →
成功 mark_done / 失敗 mark_failed（含 backoff 排下次）。

handler dispatch 走 callable registry 避免循環依賴：
``infrastructure/outbox/handlers.py`` 註冊 ``event_type -> async fn(event) -> None``，
失敗時 raise，drain 統一 catch + mark_failed。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

from src.domain.outbox.entity import OutboxEvent
from src.domain.outbox.repository import OutboxEventRepository

logger = structlog.get_logger(__name__)

OutboxHandler = Callable[[OutboxEvent], Awaitable[None]]


@dataclass(frozen=True)
class DrainOutboxResult:
    claimed: int
    succeeded: int
    failed: int
    skipped_no_handler: int


class DrainOutboxUseCase:
    """週期性撈取 + 處理 outbox 事件。"""

    def __init__(
        self,
        outbox_repo: OutboxEventRepository,
        handlers: dict[str, OutboxHandler],
        worker_id: str = "drain-outbox",
        batch_size: int = 50,
        lease_timeout_seconds: int = 300,
    ) -> None:
        self._outbox_repo = outbox_repo
        self._handlers = handlers
        self._worker_id = worker_id
        self._batch_size = batch_size
        self._lease_timeout_seconds = lease_timeout_seconds

    async def execute(self) -> DrainOutboxResult:
        events = await self._outbox_repo.claim_batch(
            worker_id=self._worker_id,
            batch_size=self._batch_size,
            lease_timeout_seconds=self._lease_timeout_seconds,
        )
        if not events:
            return DrainOutboxResult(0, 0, 0, 0)

        succeeded = 0
        failed = 0
        skipped = 0

        for event in events:
            handler = self._handlers.get(event.event_type)
            if handler is None:
                # 未註冊 handler — 視為 dead 避免無限重試
                event.mark_failed(
                    f"no handler registered for {event.event_type}"
                )
                # force dead 而非 retry
                event.attempts = event.max_attempts
                event.status = "dead"
                await self._outbox_repo.update(event)
                skipped += 1
                logger.warning(
                    "outbox.handler.missing",
                    event_id=event.id,
                    event_type=event.event_type,
                )
                continue

            try:
                await handler(event)
                event.mark_done()
                await self._outbox_repo.update(event)
                succeeded += 1
                logger.info(
                    "outbox.event.done",
                    event_id=event.id,
                    event_type=event.event_type,
                )
            except Exception as exc:  # noqa: BLE001
                event.mark_failed(str(exc))
                await self._outbox_repo.update(event)
                failed += 1
                logger.warning(
                    "outbox.event.failed",
                    event_id=event.id,
                    event_type=event.event_type,
                    attempts=event.attempts,
                    status=event.status,
                    error=str(exc)[:200],
                )

        return DrainOutboxResult(
            claimed=len(events),
            succeeded=succeeded,
            failed=failed,
            skipped_no_handler=skipped,
        )
