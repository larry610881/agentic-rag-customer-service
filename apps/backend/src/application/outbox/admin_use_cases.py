"""Admin DLQ Operations — Phase E

提供 outbox 後台四個基本操作：
- ListDeadLetter — 列 status=dead 事件（filter by event_type / tenant_id）
- RequeueOutboxEvent — DLQ 事件重排（reset attempts → pending → 等下一輪 drain）
- BulkRequeueOutboxEvent — 一次重排多筆（by event_type filter，limit 上限）
- AbandonOutboxEvent — 永久放棄（hard delete row）
- GetOutboxStats — 各 status 計數 + lag，給 admin dashboard panel
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.domain.outbox.entity import OutboxEvent, OutboxEventStatus
from src.domain.outbox.repository import OutboxEventRepository
from src.domain.shared.exceptions import EntityNotFoundError

logger = structlog.get_logger(__name__)


# ── Stats ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OutboxStats:
    pending_count: int
    in_progress_count: int
    done_count: int
    dead_count: int
    oldest_pending_age_seconds: float | None


class GetOutboxStatsUseCase:
    def __init__(self, outbox_repo: OutboxEventRepository) -> None:
        self._repo = outbox_repo

    async def execute(self) -> OutboxStats:
        return OutboxStats(
            pending_count=await self._repo.count_by_status(
                OutboxEventStatus.PENDING.value
            ),
            in_progress_count=await self._repo.count_by_status(
                OutboxEventStatus.IN_PROGRESS.value
            ),
            done_count=await self._repo.count_by_status(
                OutboxEventStatus.DONE.value
            ),
            dead_count=await self._repo.count_by_status(
                OutboxEventStatus.DEAD.value
            ),
            oldest_pending_age_seconds=await self._repo
            .oldest_pending_age_seconds(),
        )


# ── List DLQ ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ListDeadLetterQuery:
    event_type: str | None = None
    tenant_id: str | None = None
    limit: int = 100
    offset: int = 0


class ListDeadLetterUseCase:
    def __init__(self, outbox_repo: OutboxEventRepository) -> None:
        self._repo = outbox_repo

    async def execute(
        self, query: ListDeadLetterQuery
    ) -> list[OutboxEvent]:
        return await self._repo.list_dead_letter(
            event_type=query.event_type,
            tenant_id=query.tenant_id,
            limit=query.limit,
            offset=query.offset,
        )


# ── Requeue (single + bulk) ───────────────────────────────────────


@dataclass(frozen=True)
class RequeueOutboxEventCommand:
    event_id: str
    actor: str = ""


class RequeueOutboxEventUseCase:
    def __init__(self, outbox_repo: OutboxEventRepository) -> None:
        self._repo = outbox_repo

    async def execute(self, command: RequeueOutboxEventCommand) -> OutboxEvent:
        event = await self._repo.find_by_id(command.event_id)
        if event is None:
            raise EntityNotFoundError("outbox_event", command.event_id)
        # 注意：requeue 不檢查當前狀態 — admin 可能想把 in_progress 卡死的也重排
        event.requeue()
        await self._repo.update(event)
        logger.info(
            "outbox.admin.requeue",
            event_id=command.event_id,
            actor=command.actor,
            event_type=event.event_type,
        )
        return event


@dataclass(frozen=True)
class BulkRequeueDeadLetterCommand:
    event_type: str | None = None  # None = 不限類型
    tenant_id: str | None = None
    limit: int = 100               # 一次最多重排多少筆，避免 OOM
    actor: str = ""


@dataclass(frozen=True)
class BulkRequeueResult:
    requeued_count: int
    event_ids: list[str]


class BulkRequeueDeadLetterUseCase:
    def __init__(
        self,
        outbox_repo: OutboxEventRepository,
        list_dlq_uc: ListDeadLetterUseCase,
        requeue_uc: RequeueOutboxEventUseCase,
    ) -> None:
        self._repo = outbox_repo
        self._list_dlq = list_dlq_uc
        self._requeue = requeue_uc

    async def execute(
        self, command: BulkRequeueDeadLetterCommand
    ) -> BulkRequeueResult:
        events = await self._list_dlq.execute(
            ListDeadLetterQuery(
                event_type=command.event_type,
                tenant_id=command.tenant_id,
                limit=command.limit,
            )
        )
        ids: list[str] = []
        for e in events:
            await self._requeue.execute(
                RequeueOutboxEventCommand(event_id=e.id, actor=command.actor)
            )
            ids.append(e.id)
        logger.info(
            "outbox.admin.bulk_requeue",
            count=len(ids),
            event_type=command.event_type,
            tenant_id=command.tenant_id,
            actor=command.actor,
        )
        return BulkRequeueResult(requeued_count=len(ids), event_ids=ids)


# ── Abandon (hard delete) ─────────────────────────────────────────


@dataclass(frozen=True)
class AbandonOutboxEventCommand:
    event_id: str
    actor: str = ""
    reason: str = ""


class AbandonOutboxEventUseCase:
    def __init__(self, outbox_repo: OutboxEventRepository) -> None:
        self._repo = outbox_repo

    async def execute(self, command: AbandonOutboxEventCommand) -> None:
        event = await self._repo.find_by_id(command.event_id)
        if event is None:
            raise EntityNotFoundError("outbox_event", command.event_id)
        await self._repo.delete(command.event_id)
        logger.info(
            "outbox.admin.abandon",
            event_id=command.event_id,
            actor=command.actor,
            reason=command.reason[:200],
            event_type=event.event_type,
            attempts=event.attempts,
        )
