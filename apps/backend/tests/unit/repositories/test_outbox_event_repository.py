"""SQLAlchemyOutboxEventRepository — lease 撈取、DLQ 篩選與狀態更新（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.domain.outbox.entity import OutboxEvent
from src.infrastructure.db.models.outbox_event_model import OutboxEventModel
from src.infrastructure.db.repositories.outbox_event_repository import (
    SQLAlchemyOutboxEventRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> OutboxEventModel:
    data: dict = {
        "id": "ev-1",
        "tenant_id": "tenant-a",
        "aggregate_type": "document",
        "aggregate_id": "doc-1",
        "event_type": "vector.delete",
        "payload": {"collection": "kb_1"},
        "doc_watermark_ts": None,
        "status": "pending",
        "attempts": 0,
        "max_attempts": 8,
        "next_attempt_at": T0,
        "last_error": None,
        "locked_by": None,
        "locked_at": None,
        "created_at": T0,
        "completed_at": None,
    }
    data.update(over)
    return OutboxEventModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyOutboxEventRepository:
    return SQLAlchemyOutboxEventRepository(session)  # type: ignore[arg-type]


def test_save_adds_without_commit(session, repo):
    _run(repo.save(OutboxEvent(id="ev-1", tenant_id="tenant-a", event_type="x")))
    (row,) = session.added
    assert (row.id, row.tenant_id, row.event_type) == ("ev-1", "tenant-a", "x")
    assert session.commits == 0  # caller 的 atomic() 決定交易邊界


def test_claim_batch_uses_skip_locked_and_expired_lease(session, repo):
    session.queue_result([_model(), _model(id="ev-2")])

    events = _run(repo.claim_batch("worker-1", batch_size=10, lease_timeout_seconds=60))

    select_sql, update_sql = session.all_sql()
    assert "FOR UPDATE SKIP LOCKED" in select_sql
    assert "outbox_events.status = 'pending'" in select_sql
    assert "outbox_events.status = 'in_progress'" in select_sql
    assert "outbox_events.locked_at <" in select_sql
    assert "LIMIT 10" in select_sql
    assert "outbox_events.id IN ('ev-1', 'ev-2')" in update_sql
    assert "locked_by='worker-1'" in update_sql.replace(" ", "")
    assert [e.status for e in events] == ["in_progress", "in_progress"]
    assert {e.locked_by for e in events} == {"worker-1"}
    assert events[0].payload == {"collection": "kb_1"}


def test_claim_batch_empty_does_not_update(session, repo):
    assert _run(repo.claim_batch("w")) == []
    assert len(session.statements) == 1


def test_update_and_delete_target_single_event(session, repo):
    ev = OutboxEvent(id="ev-1", status="done", attempts=2, completed_at=T0)
    _run(repo.update(ev))
    sql = session.sql()
    assert "UPDATE outbox_events" in sql and "outbox_events.id = 'ev-1'" in sql
    assert "status='done'" in sql.replace(" ", "")

    _run(repo.delete("ev-1"))
    assert "DELETE FROM outbox_events" in session.sql()
    assert "outbox_events.id = 'ev-1'" in session.sql()


def test_find_by_id(session, repo):
    session.queue_result([_model()])
    ev = _run(repo.find_by_id("ev-1"))
    assert ev is not None and ev.tenant_id == "tenant-a"
    assert _run(repo.find_by_id("none")) is None


def test_list_dead_letter_filters(session, repo):
    session.queue_result([_model(status="dead")])
    evs = _run(
        repo.list_dead_letter(
            event_type="vector.delete", tenant_id="tenant-a", limit=5, offset=1
        )
    )
    sql = session.sql()
    assert "outbox_events.status = 'dead'" in sql
    assert "outbox_events.event_type = 'vector.delete'" in sql
    assert "outbox_events.tenant_id = 'tenant-a'" in sql
    assert len(evs) == 1

    _run(repo.list_dead_letter())
    assert "outbox_events.tenant_id =" not in session.sql()


def test_count_by_status_and_oldest_pending_age(session, repo):
    session.queue_result([5])
    assert _run(repo.count_by_status("pending")) == 5
    assert "outbox_events.status = 'pending'" in session.sql()

    assert _run(repo.oldest_pending_age_seconds()) is None

    session.queue_result([datetime.now(timezone.utc) - timedelta(seconds=90)])
    age = _run(repo.oldest_pending_age_seconds())
    assert age is not None and 89 <= age <= 120
