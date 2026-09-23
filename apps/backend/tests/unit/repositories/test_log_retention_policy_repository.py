"""SQLAlchemyLogRetentionPolicyRepository — 平台 singleton 與清理條件（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.observability.log_retention_policy import LogRetentionPolicy
from src.infrastructure.db.models.log_retention_policy_model import (
    LogRetentionPolicyModel,
)
from src.infrastructure.db.repositories.log_retention_policy_repository import (
    SQLAlchemyLogRetentionPolicyRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> LogRetentionPolicyModel:
    data: dict = {
        "id": "system",
        "enabled": True,
        "retention_days": 14,
        "cleanup_hour": 4,
        "cleanup_interval_hours": 12,
        "last_cleanup_at": T0,
        "deleted_count_last": 99,
        "updated_at": T0,
    }
    data.update(over)
    return LogRetentionPolicyModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyLogRetentionPolicyRepository:
    return SQLAlchemyLogRetentionPolicyRepository(session)  # type: ignore[arg-type]


def test_get_reads_system_row(session, repo):
    assert _run(repo.get()) is None
    assert "log_retention_policies.id = 'system'" in session.sql(0)
    session.queue_result([_model()])
    policy = _run(repo.get())
    assert policy is not None
    assert (policy.retention_days, policy.cleanup_hour) == (14, 4)
    assert policy.cleanup_interval_hours == 12
    assert policy.deleted_count_last == 99


def test_save_new_and_existing(session, repo):
    policy = LogRetentionPolicy(retention_days=7)
    assert _run(repo.save(policy)) is policy
    (added,) = session.added
    assert isinstance(added, LogRetentionPolicyModel)
    assert added.retention_days == 7

    existing = _model()
    session.get_result = existing
    _run(repo.save(LogRetentionPolicy(retention_days=30, enabled=False,
                                      deleted_count_last=5)))
    assert existing.retention_days == 30
    assert existing.enabled is False
    assert existing.deleted_count_last == 5
    assert existing.updated_at > T0


def test_cleanup_logs_before_deletes_only_older_rows(session, repo):
    session.queue_result([12])
    assert _run(repo.cleanup_logs_before(T0)) == 12
    count_sql, delete_sql = session.all_sql()
    assert "request_logs.created_at <" in count_sql
    assert delete_sql.startswith("DELETE FROM request_logs")
    assert "request_logs.created_at <" in delete_sql


def test_cleanup_logs_before_skips_delete_when_nothing(session, repo):
    assert _run(repo.cleanup_logs_before(T0)) == 0
    assert len(session.statements) == 1
