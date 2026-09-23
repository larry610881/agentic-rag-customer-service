"""SQLAlchemyTokenLedgerRepository — 帳本以 (tenant, cycle) 定位（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.ledger.entity import TokenLedger
from src.infrastructure.db.models.token_ledger_model import TokenLedgerModel
from src.infrastructure.db.repositories.token_ledger_repository import (
    SQLAlchemyTokenLedgerRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> TokenLedgerModel:
    data: dict = {
        "id": "l-1",
        "tenant_id": "tenant-a",
        "cycle_year_month": "2026-09",
        "plan_name": "pro",
        "base_total": 1000,
        "base_remaining": 400,
        "addon_remaining": -20,
        "total_used_in_cycle": 620,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return TokenLedgerModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyTokenLedgerRepository:
    return SQLAlchemyTokenLedgerRepository(session)  # type: ignore[arg-type]


def test_find_by_tenant_and_cycle_requires_both(session, repo):
    session.queue_result([_model()])
    ledger = _run(repo.find_by_tenant_and_cycle("tenant-a", "2026-09"))
    sql = session.sql()
    assert "token_ledgers.tenant_id = 'tenant-a'" in sql
    assert "token_ledgers.cycle_year_month = '2026-09'" in sql
    assert ledger is not None
    assert (ledger.base_remaining, ledger.addon_remaining) == (400, -20)
    assert ledger.total_used_in_cycle == 620
    assert _run(repo.find_by_tenant_and_cycle("tenant-b", "2026-09")) is None


def test_find_latest_by_tenant(session, repo):
    session.queue_result([_model()])
    assert _run(repo.find_latest_by_tenant("tenant-a")).id == "l-1"
    sql = session.sql()
    assert "token_ledgers.tenant_id = 'tenant-a'" in sql
    assert "ORDER BY token_ledgers.cycle_year_month DESC" in sql
    assert "LIMIT 1" in sql
    assert _run(repo.find_latest_by_tenant("tenant-b")) is None


def test_find_all_for_cycle(session, repo):
    session.queue_result([_model(), _model(id="l-2", tenant_id="tenant-b")])
    ledgers = _run(repo.find_all_for_cycle("2026-09"))
    assert "token_ledgers.cycle_year_month = '2026-09'" in session.sql()
    assert {x.tenant_id for x in ledgers} == {"tenant-a", "tenant-b"}


def test_save_new_and_update(session, repo):
    ledger = TokenLedger(
        id="l-9", tenant_id="tenant-a", cycle_year_month="2026-10", base_total=5
    )
    assert _run(repo.save(ledger)) is ledger
    (m,) = session.added
    assert (m.tenant_id, m.cycle_year_month, m.base_total) == (
        "tenant-a",
        "2026-10",
        5,
    )

    existing = _model()
    session.get_result = existing
    _run(
        repo.save(
            TokenLedger(
                id="l-1",
                tenant_id="tenant-a",
                cycle_year_month="2026-09",
                base_remaining=0,
                addon_remaining=-50,
                total_used_in_cycle=1050,
            )
        )
    )
    assert (existing.base_remaining, existing.addon_remaining) == (0, -50)
    assert existing.total_used_in_cycle == 1050
    assert existing.updated_at > T0
