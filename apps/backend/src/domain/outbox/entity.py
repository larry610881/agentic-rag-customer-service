"""Outbox Pattern — Domain Entity

Cross-system write 一致性保證：在 PG transaction 內 INSERT outbox row +
業務 SQL → commit → async worker drain 對外部系統（Milvus）套用。

Phase A 範圍：只覆蓋 vector store DELETE 類事件。UPSERT 不納入
（payload 太肥 + 失敗率低 + 有 doc.status fallback）。觸發升級閾值
見 memory/outbox-upsert-trigger-thresholds.md。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class OutboxEventStatus(str, Enum):
    """Outbox event 生命週期狀態。"""

    PENDING = "pending"            # 等 worker 撈
    IN_PROGRESS = "in_progress"    # worker 撈到 (lease holder)
    DONE = "done"                  # 已成功對外部系統套用
    DEAD = "dead"                  # 達 max_attempts，進 DLQ


class OutboxEventType(str, Enum):
    """支援的事件類型（Phase A-D 只覆蓋 vector.* DELETE）。"""

    VECTOR_DELETE = "vector.delete"                        # filter-based delete
    VECTOR_DROP_COLLECTION = "vector.drop_collection"      # 整個 collection 刪掉


@dataclass
class OutboxEvent:
    """Outbox 事件聚合根。

    `id` 是 idempotency key — 同一 id 重試不會造成 double-effect
    （搭配 handler 必須 idempotent，例如 Milvus filter delete 天然冪等）。

    `doc_watermark_ts` 用於 doc-id reuse guard（Phase C）：drain 時
    對比 doc.created_at，若 doc 是事件發布後才建立的（id 被重用）就跳過。
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    # 聚合類型：knowledge_base / document / document_source / chunk
    aggregate_type: str = ""
    aggregate_id: str = ""
    event_type: str = ""               # OutboxEventType.value
    payload: dict[str, Any] = field(default_factory=dict)
    doc_watermark_ts: datetime | None = None
    status: str = OutboxEventStatus.PENDING.value
    attempts: int = 0
    max_attempts: int = 8
    next_attempt_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_error: str | None = None
    locked_by: str | None = None
    locked_at: datetime | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime | None = None

    def mark_in_progress(self, worker_id: str) -> None:
        """Worker 撈到事件，set lease。"""
        self.status = OutboxEventStatus.IN_PROGRESS.value
        self.locked_by = worker_id
        self.locked_at = datetime.now(timezone.utc)

    def mark_done(self) -> None:
        """事件成功處理。"""
        self.status = OutboxEventStatus.DONE.value
        self.completed_at = datetime.now(timezone.utc)
        self.locked_by = None
        self.locked_at = None
        self.last_error = None

    def mark_failed(self, error: str) -> None:
        """事件處理失敗 — 增 attempts，達 max 進 DLQ，否則排下次重試。

        Backoff: ``min(2^attempts × 30s, 1h)`` — 30s, 60s, 120s, ..., 1h cap。
        """
        self.attempts += 1
        self.last_error = error[:1000]
        self.locked_by = None
        self.locked_at = None
        if self.attempts >= self.max_attempts:
            self.status = OutboxEventStatus.DEAD.value
            self.completed_at = datetime.now(timezone.utc)
        else:
            self.status = OutboxEventStatus.PENDING.value
            backoff_seconds = min(2 ** self.attempts * 30, 3600)
            self.next_attempt_at = datetime.now(timezone.utc).replace(
                microsecond=0
            )
            # 加 backoff 秒數
            from datetime import timedelta
            self.next_attempt_at = (
                datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            )

    def requeue(self) -> None:
        """DLQ 中的事件被 admin 手動重排：重置 attempts + status。"""
        self.attempts = 0
        self.status = OutboxEventStatus.PENDING.value
        self.next_attempt_at = datetime.now(timezone.utc)
        self.last_error = None
        self.locked_by = None
        self.locked_at = None
        self.completed_at = None
