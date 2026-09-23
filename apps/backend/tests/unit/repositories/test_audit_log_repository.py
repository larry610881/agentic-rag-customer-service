"""SQLAlchemyAuditLogRepository — 租戶篩選、實體範圍與 keyset 分頁（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.audit.entity import AuditEntry, encode_audit_cursor
from src.infrastructure.db.models.audit_log_model import AuditLogModel
from src.infrastructure.db.repositories.audit_log_repository import (
    SQLAlchemyAuditLogRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> AuditLogModel:
    data: dict = {
        "id": "a-1",
        "tenant_id": "tenant-a",
        "actor_user_id": "u-1",
        "entity_type": "bot",
        "entity_id": "bot-1",
        "action": "update",
        "changed_fields": None,
        "source": "api",
        "created_at": T0,
        "parent_entity_type": None,
        "parent_entity_id": None,
    }
    data.update(over)
    return AuditLogModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyAuditLogRepository:
    return SQLAlchemyAuditLogRepository(session)  # type: ignore[arg-type]


def test_append_adds_entry(session, repo):
    entry = AuditEntry(
        entity_type="worker",
        entity_id="w-1",
        action="create",
        tenant_id="tenant-a",
        parent_entity_type="bot",
        parent_entity_id="bot-1",
        changed_fields={"name": {"before": None, "after": "x"}},
    )
    _run(repo.append(entry))
    (m,) = session.added
    assert (m.tenant_id, m.parent_entity_id) == ("tenant-a", "bot-1")
    assert m.changed_fields == {"name": {"before": None, "after": "x"}}
    assert session.commits == 1


def test_list_entries_filters(session, repo):
    session.queue_result([_model()])
    (e,) = _run(
        repo.list_entries(
            tenant_id="tenant-a", entity_type="bot", entity_id="bot-1", limit=5
        )
    )
    sql = session.sql()
    assert "audit_logs.tenant_id = 'tenant-a'" in sql
    assert "audit_logs.entity_type = 'bot'" in sql
    assert "audit_logs.entity_id = 'bot-1'" in sql
    assert "LIMIT 5" in sql
    assert e.changed_fields == {}  # NULL → 空 dict

    _run(repo.list_entries())
    assert "WHERE" not in session.sql()


def test_find_by_entity_first_page(session, repo):
    session.queue_result([_model()])
    (e,) = _run(repo.find_by_entity(entity_type="bot", entity_id="bot-1", limit=3))
    sql = session.sql()
    assert "audit_logs.entity_type = 'bot'" in sql
    assert "audit_logs.entity_id = 'bot-1'" in sql
    assert "ORDER BY audit_logs.created_at DESC, audit_logs.id DESC" in sql
    assert "LIMIT 3" in sql
    assert e.entity_id == "bot-1"


def test_find_by_entity_cursor_takes_older_rows_only(session, repo):
    last = AuditEntry(
        entity_type="bot", entity_id="b", action="x", id="a-9", created_at=T0
    )
    cursor = encode_audit_cursor(last)
    _run(
        repo.find_by_entity(
            entity_type="bot", entity_id="bot-1", limit=3, cursor=cursor
        )
    )
    sql = session.sql()
    assert "audit_logs.created_at < '2026-09-01" in sql
    assert "audit_logs.id < 'a-9'" in sql


def test_find_by_entity_or_parent_unions_children(session, repo):
    session.queue_result([_model(), _model(id="a-2", entity_type="worker")])
    rows = _run(
        repo.find_by_entity_or_parent(
            entity_type="bot",
            entity_id="bot-1",
            parent_entity_type="bot",
            parent_entity_id="bot-1",
            limit=10,
        )
    )
    sql = session.sql()
    assert "audit_logs.entity_id = 'bot-1'" in sql
    assert "audit_logs.parent_entity_type = 'bot'" in sql
    assert "audit_logs.parent_entity_id = 'bot-1'" in sql
    assert " OR " in sql
    assert [r.id for r in rows] == ["a-1", "a-2"]
