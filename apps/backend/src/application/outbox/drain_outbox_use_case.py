"""Drain Outbox Use Case — Worker 端週期執行

每次 cron tick 撈 batch（含過期 lease 回收）→ 對每筆 dispatch handler →
成功 mark_done / 失敗 mark_failed（含 backoff 排下次）。

handler dispatch 走 callable registry 避免循環依賴：
``infrastructure/outbox/handlers.py`` 註冊 ``event_type -> async fn(event) -> None``，
失敗時 raise，drain 統一 catch + mark_failed。

Phase C 新增 doc-id reuse guard：對 ``aggregate_type='document'`` 且帶
``doc_watermark_ts`` 的事件，dispatch 前先查 doc 在 PG 是否已被新版重建
（通常透過 source_id 重 upload）— 若新 doc.created_at > watermark 就跳過該
事件，避免把新版誤刪。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

from src.domain.knowledge.repository import DocumentRepository
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
    skipped_id_reuse: int = 0


class DrainOutboxUseCase:
    """週期性撈取 + 處理 outbox 事件。"""

    def __init__(
        self,
        outbox_repo: OutboxEventRepository,
        handlers: dict[str, OutboxHandler],
        document_repository: DocumentRepository | None = None,
        worker_id: str = "drain-outbox",
        batch_size: int = 50,
        lease_timeout_seconds: int = 300,
    ) -> None:
        self._outbox_repo = outbox_repo
        self._handlers = handlers
        self._doc_repo = document_repository
        self._worker_id = worker_id
        self._batch_size = batch_size
        self._lease_timeout_seconds = lease_timeout_seconds

    async def _is_id_reused(self, event: OutboxEvent) -> bool:
        """Doc-id reuse guard — 若 PG 內同 doc_id 已存在新版本（created_at
        晚於 event.doc_watermark_ts），表示原 doc 已被新版重建，drain 應跳過
        此事件避免誤刪新版的 Milvus chunks。

        只對 ``aggregate_type='document'`` 且有 watermark 的事件檢查。
        ``document_source`` (source-driven bulk delete) 不適用，watermark 為
        None 時也跳過檢查。
        """
        if not self._doc_repo:
            return False
        if event.doc_watermark_ts is None:
            return False
        if event.aggregate_type != "document":
            return False
        try:
            current = await self._doc_repo.find_by_id(event.aggregate_id)
        except Exception:  # noqa: BLE001
            # 查詢失敗（DB blip）→ 不擋；交給後續 handler / retry
            return False
        if current is None:
            # PG 已無此 doc（cascade 已刪）— 正常情境，不跳過
            return False
        # 新版 created_at 晚於 watermark → id reused
        return current.created_at > event.doc_watermark_ts

    async def execute(self) -> DrainOutboxResult:
        events = await self._outbox_repo.claim_batch(
            worker_id=self._worker_id,
            batch_size=self._batch_size,
            lease_timeout_seconds=self._lease_timeout_seconds,
        )
        if not events:
            return DrainOutboxResult(0, 0, 0, 0, 0)

        succeeded = 0
        failed = 0
        skipped = 0
        skipped_id_reuse = 0

        for event in events:
            # Phase C: doc-id reuse guard
            if await self._is_id_reused(event):
                event.mark_done()  # 視為已處理，避免無限 retry
                await self._outbox_repo.update(event)
                skipped_id_reuse += 1
                logger.info(
                    "outbox.event.skipped_id_reuse",
                    event_id=event.id,
                    aggregate_id=event.aggregate_id,
                    watermark_ts=event.doc_watermark_ts.isoformat()
                    if event.doc_watermark_ts else None,
                )
                continue

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

        # Phase D observability: 一次 drain tick 摘要 + 健康指標
        # 給 GCP log-based metric 抓的事件名（穩定不要亂改）
        try:
            dlq_count = await self._outbox_repo.count_by_status("dead")
            pending_count = await self._outbox_repo.count_by_status("pending")
            lag = await self._outbox_repo.oldest_pending_age_seconds()
        except Exception:  # noqa: BLE001
            # metrics 失敗絕不擋 drain（已經處理完事件了）
            dlq_count = -1
            pending_count = -1
            lag = None

        logger.info(
            "outbox.drain.tick",
            claimed=len(events),
            succeeded=succeeded,
            failed=failed,
            skipped_no_handler=skipped,
            skipped_id_reuse=skipped_id_reuse,
            dlq_count=dlq_count,
            pending_count=pending_count,
            oldest_pending_age_seconds=lag,
        )

        return DrainOutboxResult(
            claimed=len(events),
            succeeded=succeeded,
            failed=failed,
            skipped_no_handler=skipped,
            skipped_id_reuse=skipped_id_reuse,
        )
