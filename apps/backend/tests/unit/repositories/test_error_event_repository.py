"""SQLAlchemyErrorEventRepository — 篩選條件、resolve 與清理（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.observability.error_event import ErrorEvent
from src.infrastructure.db.models.error_event_model import ErrorEventModel
from src.infrastructure.db.models.error_notification_log_model import (
    ErrorNotificationLogModel,
)
from src.infrastructure.db.repositories.error_event_repository import (
    SQLAlchemyErrorEventRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> ErrorEventModel:
    data: dict = {
        "id": "e-1",
        "fingerprint": "fp",
        "source": "backend",
        "error_type": "ValueError",
        "message": "boom",
        "stack_trace": "tb",
        "request_id": "r-1",
        "path": "/x",
        "method": "GET",
        "status_code": 500,
        "tenant_id": "tenant-a",
        "user_agent": "ua",
        "extra": {"k": 1},
        "resolved": False,
        "resolved_at": None,
        "resolved_by": None,
        "created_at": T0,
    }
    data.update(over)
    return ErrorEventModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyErrorEventRepository:
    return SQLAlchemyErrorEventRepository(session)  # type: ignore[arg-type]


def test_save_adds_event_with_tenant(session, repo):
    ev = ErrorEvent(
        id="e-1",
        fingerprint="fp",
        source="frontend",
        error_type="TypeError",
        message="m",
        tenant_id="tenant-a",
    )
    assert _run(repo.save(ev)) is ev
    (m,) = session.added
    assert (m.tenant_id, m.source, m.fingerprint) == ("tenant-a", "frontend", "fp")


def test_get_by_id_maps(session, repo):
    session.queue_result([_model()])
    ev = _run(repo.get_by_id("e-1"))
    assert "error_events.id = 'e-1'" in session.sql()
    assert ev is not None and ev.tenant_id == "tenant-a" and ev.extra == {"k": 1}
    assert _run(repo.get_by_id("none")) is None


def test_list_events_applies_every_filter_to_page_and_count(session, repo):
    session.queue_result([2])
    session.queue_result([_model(), _model(id="e-2")])
    events, total = _run(
        repo.list_events(
            source="backend",
            resolved=False,
            fingerprint="fp",
            tenant_id="tenant-a",
            method="POST",
            limit=10,
            offset=5,
        )
    )
    count_sql, page_sql = session.all_sql()
    for sql in (count_sql, page_sql):
        assert "error_events.tenant_id = 'tenant-a'" in sql
        assert "error_events.source = 'backend'" in sql
        assert "error_events.resolved = false" in sql
        assert "error_events.fingerprint = 'fp'" in sql
        assert "error_events.method = 'POST'" in sql
    assert "LIMIT 10" in page_sql and "OFFSET 5" in page_sql
    assert total == 2 and [e.id for e in events] == ["e-1", "e-2"]


def test_list_events_without_filters(session, repo):
    events, total = _run(repo.list_events())
    assert (events, total) == ([], 0)
    assert "WHERE" not in session.sql(0)


def test_resolve_marks_resolved(session, repo):
    m = _model()
    session.get_result = m
    ev = _run(repo.resolve("e-1", "admin@x"))
    assert ev is not None and ev.resolved is True
    assert m.resolved_by == "admin@x" and m.resolved_at is not None
    assert session.commits == 1

    session.get_result = None
    assert _run(repo.resolve("missing", "x")) is None


def test_count_by_fingerprint(session, repo):
    session.queue_result([3])
    assert _run(repo.count_by_fingerprint("fp")) == 3
    assert "error_events.fingerprint = 'fp'" in session.sql()


def test_notification_log(session, repo):
    session.queue_result([T0])
    assert _run(repo.last_notified_at("fp", "ch-1")) == T0
    sql = session.sql()
    assert "error_notification_logs.fingerprint = 'fp'" in sql
    assert "error_notification_logs.channel_id = 'ch-1'" in sql

    _run(repo.record_notification("fp", "ch-1"))
    (log,) = session.added
    assert isinstance(log, ErrorNotificationLogModel)
    assert (log.fingerprint, log.channel_id) == ("fp", "ch-1")


def test_cleanup_before_deletes_only_when_rows_exist(session, repo):
    assert _run(repo.cleanup_before(T0)) == 0
    assert len(session.statements) == 1  # 只數，不刪

    session.queue_result([4])
    assert _run(repo.cleanup_before(T0)) == 4
    delete_sql = session.sql()
    assert "DELETE FROM error_events" in delete_sql
    assert "error_events.created_at < '2026-09-01" in delete_sql
