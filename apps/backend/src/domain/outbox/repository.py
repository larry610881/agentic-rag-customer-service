"""Outbox Repository Interface（Domain layer）

Implementations live in infrastructure/db/repositories/outbox_event_repository.py
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.outbox.entity import OutboxEvent


class OutboxEventRepository(ABC):
    """Outbox 事件存取介面。

    寫入路徑必須與業務 SQL 同 transaction（atomic 保證），因此 ``save()``
    不自帶 commit — 由 caller 透過 ``atomic(session)`` context manager 控制。
    """

    @abstractmethod
    async def save(self, event: OutboxEvent) -> None:
        """INSERT 新事件（不 commit）。"""
        ...

    @abstractmethod
    async def claim_batch(
        self,
        worker_id: str,
        batch_size: int = 50,
        lease_timeout_seconds: int = 300,
    ) -> list[OutboxEvent]:
        """撈 batch 並 set lease（SELECT FOR UPDATE SKIP LOCKED）。

        - 撈出 ``status=pending AND next_attempt_at <= NOW()`` 的事件
        - 同時把 ``locked_at < NOW() - lease_timeout_seconds`` 的
          ``in_progress`` 事件視為 lease 過期，回收
        - 把撈到的事件 mark_in_progress(worker_id) 並更新 DB
        """
        ...

    @abstractmethod
    async def update(self, event: OutboxEvent) -> None:
        """更新事件狀態（done / failed / requeue 後呼叫）。

        包含自己的 commit — drain worker 一筆一筆獨立 commit，避免
        某筆失敗影響其他筆已成功的狀態寫入。
        """
        ...

    @abstractmethod
    async def find_by_id(self, event_id: str) -> OutboxEvent | None:
        """admin DLQ retry / abandon 用。"""
        ...

    @abstractmethod
    async def list_dead_letter(
        self,
        *,
        event_type: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OutboxEvent]:
        """DLQ 列表（Phase E admin UI 用）。"""
        ...

    @abstractmethod
    async def count_by_status(self, status: str) -> int:
        """Stats panel + 告警用。"""
        ...
