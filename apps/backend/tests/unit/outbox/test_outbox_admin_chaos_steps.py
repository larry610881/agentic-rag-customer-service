"""Outbox admin DLQ + chaos BDD step definitions（Phase E）."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.outbox.admin_use_cases import (
    AbandonOutboxEventCommand,
    AbandonOutboxEventUseCase,
    GetOutboxStatsUseCase,
    RequeueOutboxEventCommand,
    RequeueOutboxEventUseCase,
)
from src.application.outbox.drain_outbox_use_case import DrainOutboxUseCase
from src.domain.outbox.entity import (
    OutboxEvent,
    OutboxEventStatus,
    OutboxEventType,
)
from src.domain.outbox.repository import OutboxEventRepository

scenarios("unit/outbox/outbox_admin_chaos.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── In-memory fake repo（含 admin 操作支援） ─────────────────────


class _InMemoryRepo(OutboxEventRepository):
    def __init__(self) -> None:
        self.events: dict[str, OutboxEvent] = {}

    async def save(self, event: OutboxEvent) -> None:
        self.events[event.id] = event

    async def claim_batch(
        self, worker_id: str, batch_size: int = 50,
        lease_timeout_seconds: int = 300,
    ) -> list[OutboxEvent]:
        now = datetime.now(timezone.utc)
        deadline = now - timedelta(seconds=lease_timeout_seconds)
        claimed: list[OutboxEvent] = []
        for ev in self.events.values():
            ready = (
                ev.status == OutboxEventStatus.PENDING.value
                and ev.next_attempt_at <= now
            ) or (
                ev.status == OutboxEventStatus.IN_PROGRESS.value
                and ev.locked_at is not None
                and ev.locked_at < deadline
            )
            if ready:
                ev.mark_in_progress(worker_id)
                claimed.append(ev)
                if len(claimed) >= batch_size:
                    break
        return claimed

    async def update(self, event: OutboxEvent) -> None:
        self.events[event.id] = event

    async def find_by_id(self, event_id: str) -> OutboxEvent | None:
        return self.events.get(event_id)

    async def list_dead_letter(
        self, *, event_type: str | None = None,
        tenant_id: str | None = None, limit: int = 100, offset: int = 0,
    ) -> list[OutboxEvent]:
        items = [
            e for e in self.events.values()
            if e.status == OutboxEventStatus.DEAD.value
            and (not event_type or e.event_type == event_type)
            and (not tenant_id or e.tenant_id == tenant_id)
        ]
        return items[offset : offset + limit]

    async def count_by_status(self, status: str) -> int:
        return sum(1 for e in self.events.values() if e.status == status)

    async def oldest_pending_age_seconds(self) -> float | None:
        pending = [
            e for e in self.events.values()
            if e.status == OutboxEventStatus.PENDING.value
        ]
        if not pending:
            return None
        oldest = min(p.created_at for p in pending)
        return max(
            0.0, (datetime.now(timezone.utc) - oldest).total_seconds()
        )

    async def delete(self, event_id: str) -> None:
        self.events.pop(event_id, None)


@pytest.fixture
def context() -> dict:
    return {"handler_call_count": 0}


# ── Given ────────────────────────────────────────────────────────


@given(parsers.parse(
    "outbox 有 1 筆 attempts={start_attempts:d} max_attempts={max_attempts:d} "
    "的 pending 事件"
))
def repo_with_high_attempt(context, start_attempts: int, max_attempts: int):
    context["repo"] = _InMemoryRepo()
    event = OutboxEvent(
        tenant_id="t-1",
        aggregate_type="document",
        aggregate_id="doc-1",
        event_type=OutboxEventType.VECTOR_DELETE.value,
        payload={"collection": "kb_test", "filters": {"document_id": ["doc-1"]}},
    )
    event.attempts = start_attempts
    event.max_attempts = max_attempts
    _run(context["repo"].save(event))
    context["event_id"] = event.id


@given(parsers.parse(
    "outbox 有 1 筆 status=dead attempts={attempts:d} 的事件"
))
def repo_with_dead_event(context, attempts: int):
    context["repo"] = _InMemoryRepo()
    event = OutboxEvent(
        tenant_id="t-1",
        aggregate_type="document",
        aggregate_id="doc-1",
        event_type=OutboxEventType.VECTOR_DELETE.value,
        payload={"collection": "kb_test", "filters": {"document_id": ["doc-1"]}},
    )
    event.attempts = attempts
    event.status = OutboxEventStatus.DEAD.value
    _run(context["repo"].save(event))
    context["event_id"] = event.id


@given("handler 對應 vector.delete 會拋 ConnectionError")
def handler_fail(context):
    async def _fail(event):
        context["handler_call_count"] += 1
        raise ConnectionError("milvus down")

    context["handlers"] = {OutboxEventType.VECTOR_DELETE.value: _fail}


@given("handler 對應 vector.delete 改為會成功執行")
def handler_success_after(context):
    async def _ok(event):
        context["handler_call_count"] += 1

    context["handlers"] = {OutboxEventType.VECTOR_DELETE.value: _ok}


# ── When ─────────────────────────────────────────────────────────


@when("drain worker 跑一次")
def run_drain(context):
    drain = DrainOutboxUseCase(
        outbox_repo=context["repo"],
        handlers=context["handlers"],
        worker_id="test-worker",
    )
    _run(drain.execute())


@when("admin 對該事件 requeue")
def admin_requeue(context):
    uc = RequeueOutboxEventUseCase(outbox_repo=context["repo"])
    _run(uc.execute(RequeueOutboxEventCommand(
        event_id=context["event_id"], actor="admin-test",
    )))


@when(parsers.parse('admin 對該事件 abandon 並備註原因 "{reason}"'))
def admin_abandon(context, reason: str):
    uc = AbandonOutboxEventUseCase(outbox_repo=context["repo"])
    _run(uc.execute(AbandonOutboxEventCommand(
        event_id=context["event_id"], actor="admin-test", reason=reason,
    )))


# ── Then ─────────────────────────────────────────────────────────


@then(parsers.parse('該事件 status 應為 "{status}"'))
def assert_status(context, status: str):
    event = context["repo"].events[context["event_id"]]
    assert event.status == status


@then(parsers.parse("該事件 attempts 應為 {expected:d}"))
def assert_attempts(context, expected: int):
    event = context["repo"].events[context["event_id"]]
    assert event.attempts == expected


@then(parsers.parse("outbox stats dead_count 應為 {expected:d}"))
def assert_stats_dead(context, expected: int):
    uc = GetOutboxStatsUseCase(outbox_repo=context["repo"])
    stats = _run(uc.execute())
    assert stats.dead_count == expected


@then("該事件應從 outbox 完全消失")
def assert_event_gone(context):
    assert context["event_id"] not in context["repo"].events
