"""Outbox publish + drain BDD step definitions."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.outbox.drain_outbox_use_case import DrainOutboxUseCase
from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.outbox.entity import (
    OutboxEvent,
    OutboxEventStatus,
    OutboxEventType,
)
from src.domain.outbox.events import vector_delete_event
from src.domain.outbox.repository import OutboxEventRepository

scenarios("unit/outbox/outbox_publish_drain.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── In-memory fake repository（unit test 用） ────────────────────────


class _InMemoryOutboxRepo(OutboxEventRepository):
    def __init__(self) -> None:
        self.events: dict[str, OutboxEvent] = {}
        self.save_calls = 0

    async def save(self, event: OutboxEvent) -> None:
        self.save_calls += 1
        self.events[event.id] = event

    async def claim_batch(
        self,
        worker_id: str,
        batch_size: int = 50,
        lease_timeout_seconds: int = 300,
    ) -> list[OutboxEvent]:
        now = datetime.now(timezone.utc)
        lease_deadline = now - timedelta(seconds=lease_timeout_seconds)
        claimed: list[OutboxEvent] = []
        for ev in self.events.values():
            ready = (
                ev.status == OutboxEventStatus.PENDING.value
                and ev.next_attempt_at <= now
            ) or (
                ev.status == OutboxEventStatus.IN_PROGRESS.value
                and ev.locked_at is not None
                and ev.locked_at < lease_deadline
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
        self,
        *,
        event_type: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OutboxEvent]:
        return [
            e for e in self.events.values()
            if e.status == OutboxEventStatus.DEAD.value
        ][offset : offset + limit]

    async def count_by_status(self, status: str) -> int:
        return sum(1 for e in self.events.values() if e.status == status)


@pytest.fixture
def context() -> dict:
    return {"handler_call_count": 0}


# ── Given ───────────────────────────────────────────────────────────


@given("一個空的 outbox repository")
def empty_repo(context) -> None:
    context["repo"] = _InMemoryOutboxRepo()
    context["publish_uc"] = PublishOutboxEventUseCase(context["repo"])


@given("outbox 有 1 筆 vector.delete pending 事件")
def repo_with_one_pending_event(context) -> None:
    context["repo"] = _InMemoryOutboxRepo()
    event = vector_delete_event(
        tenant_id="t-1",
        aggregate_type="document",
        aggregate_id="doc-1",
        collection="kb_test",
        filters={"document_id": "doc-1"},
    )
    _run(context["repo"].save(event))
    context["event_id"] = event.id


@given(parsers.parse(
    "outbox 有 1 筆 attempts={start_attempts:d} max_attempts={max_attempts:d} "
    "的 pending 事件"
))
def repo_with_high_attempt_event(
    context, start_attempts: int, max_attempts: int
) -> None:
    context["repo"] = _InMemoryOutboxRepo()
    event = vector_delete_event(
        tenant_id="t-1",
        aggregate_type="document",
        aggregate_id="doc-1",
        collection="kb_test",
        filters={"document_id": "doc-1"},
    )
    event.attempts = start_attempts
    event.max_attempts = max_attempts
    _run(context["repo"].save(event))
    context["event_id"] = event.id


@given(parsers.parse(
    'outbox 有 1 筆 event_type="{event_type}" 的 pending 事件'
))
def repo_with_unknown_event_type(context, event_type: str) -> None:
    context["repo"] = _InMemoryOutboxRepo()
    event = OutboxEvent(
        tenant_id="t-1",
        aggregate_type="document",
        aggregate_id="doc-1",
        event_type=event_type,
        payload={"collection": "kb_test", "filters": {"id": "x"}},
    )
    _run(context["repo"].save(event))
    context["event_id"] = event.id


@given("handler 對應 vector.delete 會成功執行")
def handler_success(context) -> None:
    async def _ok(event: OutboxEvent) -> None:
        context["handler_call_count"] += 1

    context["handlers"] = {
        OutboxEventType.VECTOR_DELETE.value: _ok,
    }


@given("handler 對應 vector.delete 會拋 ConnectionError")
def handler_failure(context) -> None:
    async def _fail(event: OutboxEvent) -> None:
        context["handler_call_count"] += 1
        raise ConnectionError("milvus down")

    context["handlers"] = {
        OutboxEventType.VECTOR_DELETE.value: _fail,
    }


@given("handler registry 不含該 event_type")
def empty_handlers(context) -> None:
    context["handlers"] = {}


# ── When ────────────────────────────────────────────────────────────


@when("應用層 publish 一個 vector.delete 事件")
def publish_event(context) -> None:
    event = vector_delete_event(
        tenant_id="t-1",
        aggregate_type="document",
        aggregate_id="doc-1",
        collection="kb_test",
        filters={"document_id": "doc-1"},
    )
    _run(context["publish_uc"].execute(event))
    context["event_id"] = event.id


@when("drain worker 跑一次")
def run_drain(context) -> None:
    drain = DrainOutboxUseCase(
        outbox_repo=context["repo"],
        handlers=context["handlers"],
        worker_id="test-worker",
    )
    context["drain_result"] = _run(drain.execute())


# ── Then ────────────────────────────────────────────────────────────


@then(parsers.parse('outbox repository 應收到一筆 status="{status}" 的事件'))
def assert_one_event_with_status(context, status: str) -> None:
    repo: _InMemoryOutboxRepo = context["repo"]
    assert len(repo.events) == 1
    event = next(iter(repo.events.values()))
    assert event.status == status


@then(parsers.parse("事件的 attempts 應為 {expected:d}"))
def assert_attempts(context, expected: int) -> None:
    repo: _InMemoryOutboxRepo = context["repo"]
    event = next(iter(repo.events.values()))
    assert event.attempts == expected


@then(parsers.parse('該事件 status 應為 "{status}"'))
def assert_event_status(context, status: str) -> None:
    repo: _InMemoryOutboxRepo = context["repo"]
    event = repo.events[context["event_id"]]
    assert event.status == status, (
        f"expected {status}, got {event.status} attempts={event.attempts}"
    )


@then(parsers.parse("該事件 attempts 應為 {expected:d}"))
def assert_event_attempts(context, expected: int) -> None:
    repo: _InMemoryOutboxRepo = context["repo"]
    event = repo.events[context["event_id"]]
    assert event.attempts == expected


@then("該事件 next_attempt_at 應晚於現在")
def assert_next_attempt_in_future(context) -> None:
    repo: _InMemoryOutboxRepo = context["repo"]
    event = repo.events[context["event_id"]]
    assert event.next_attempt_at > datetime.now(timezone.utc)


@then(parsers.parse("handler 應被呼叫 {expected:d} 次"))
def assert_handler_calls(context, expected: int) -> None:
    assert context["handler_call_count"] == expected
