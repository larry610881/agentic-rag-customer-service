"""SQLAlchemyQuotaAlertLogRepository — 租戶過濾條件、冪等寫入（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from src.domain.billing.quota_alert import QuotaAlertLog
from src.infrastructure.db.models.quota_alert_log_model import QuotaAlertLogModel
from src.infrastructure.db.repositories.quota_alert_log_repository import (
    SQLAlchemyQuotaAlertLogRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> QuotaAlertLogModel:
    data: dict = {
        "id": "al-1",
        "tenant_id": "tenant-a",
        "cycle_year_month": "2026-09",
        "alert_type": "base_warning_80",
        "used_ratio": Decimal("0.8123"),
        "message": None,
        "delivered_to_email": False,
        "created_at": T0,
    }
    data.update(over)
    return QuotaAlertLogModel(**data)


class _UniqueViolationSession(SpySession):
    def __init__(self) -> None:
        super().__init__()
        self.rollbacks = 0

    async def commit(self) -> None:
        raise IntegrityError("INSERT", {}, Exception("uq_quota_alert"))

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyQuotaAlertLogRepository:
    return SQLAlchemyQuotaAlertLogRepository(session)  # type: ignore[arg-type]


def test_save_if_new_adds_and_returns_alert(session, repo):
    alert = QuotaAlertLog(id="al-9", tenant_id="tenant-a", cycle_year_month="2026-09",
                          alert_type="base_warning_80", message="")
    assert _run(repo.save_if_new(alert)) is alert
    (added,) = session.added
    assert isinstance(added, QuotaAlertLogModel)
    assert (added.tenant_id, added.alert_type) == ("tenant-a", "base_warning_80")
    assert added.message is None


def test_save_if_new_duplicate_returns_none_and_rolls_back():
    session = _UniqueViolationSession()
    repo = SQLAlchemyQuotaAlertLogRepository(session)  # type: ignore[arg-type]
    alert = QuotaAlertLog(tenant_id="tenant-a", cycle_year_month="2026-09",
                          alert_type="base_warning_80")
    assert _run(repo.save_if_new(alert)) is None
    assert session.rollbacks == 1


def test_list_recent_with_tenant_maps_entity(session, repo):
    session.queue_result([_model()])
    (al,) = _run(repo.list_recent(limit=5, offset=0, tenant_id="tenant-a"))
    sql = session.sql(0)
    assert "quota_alert_logs.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 5" in sql
    assert al.id == "al-1" and al.tenant_id == "tenant-a"
    assert al.used_ratio == Decimal("0.8123")
    assert al.message == ""


def test_list_recent_and_count_without_tenant_are_admin_views(session, repo):
    _run(repo.list_recent())
    assert "WHERE" not in session.sql(-1)
    session.queue_result([2])
    assert _run(repo.count_recent("tenant-a")) == 2
    assert "quota_alert_logs.tenant_id = 'tenant-a'" in session.sql(-1)
    assert _run(repo.count_recent()) == 0
    assert "WHERE" not in session.sql(-1)


def test_find_by_tenant_and_cycle(session, repo):
    _run(repo.find_by_tenant_and_cycle("tenant-a", "2026-09"))
    sql = session.sql(0)
    assert "quota_alert_logs.tenant_id = 'tenant-a'" in sql
    assert "quota_alert_logs.cycle_year_month = '2026-09'" in sql


def test_find_undelivered(session, repo):
    session.queue_result([_model()])
    (al,) = _run(repo.find_undelivered(limit=7))
    sql = session.sql(0)
    assert "quota_alert_logs.delivered_to_email IS false" in sql
    assert "LIMIT 7" in sql
    assert al.delivered_to_email is False


def test_mark_delivered(session, repo):
    _run(repo.mark_delivered("missing"))
    existing = _model()
    session.get_result = existing
    _run(repo.mark_delivered("al-1"))
    assert existing.delivered_to_email is True
