"""SQLAlchemyTokenLedgerTopupRepository — 租戶＋週期過濾與映射（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.ledger.topup_entity import TokenLedgerTopup
from src.infrastructure.db.models.token_ledger_topup_model import (
    TokenLedgerTopupModel,
)
from src.infrastructure.db.repositories.token_ledger_topup_repository import (
    SQLAlchemyTokenLedgerTopupRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyTokenLedgerTopupRepository:
    return SQLAlchemyTokenLedgerTopupRepository(session)  # type: ignore[arg-type]


@pytest.mark.parametrize("method", ["sum_amount_in_cycle", "sum_points_in_cycle"])
def test_sums_filter_tenant_and_cycle(session, repo, method):
    session.queue_result([1500])
    assert _run(getattr(repo, method)("tenant-a", "2026-09")) == 1500
    sql = session.sql(0)
    assert "token_ledger_topups.tenant_id = 'tenant-a'" in sql
    assert "token_ledger_topups.cycle_year_month = '2026-09'" in sql
    assert "coalesce(sum(" in sql


def test_find_in_cycle_filters_and_maps(session, repo):
    session.queue_result([TokenLedgerTopupModel(
        id="tu-1", tenant_id="tenant-a", cycle_year_month="2026-09", amount=-200,
        amount_points=None, reason="manual_adjust", pricing_version="v3", created_at=T0,
    )])
    (tu,) = _run(repo.find_in_cycle("tenant-a", "2026-09"))
    sql = session.sql(0)
    assert "token_ledger_topups.tenant_id = 'tenant-a'" in sql
    assert "token_ledger_topups.cycle_year_month = '2026-09'" in sql
    assert (tu.id, tu.tenant_id, tu.amount) == ("tu-1", "tenant-a", -200)
    assert tu.amount_points == 0
    assert (tu.reason, tu.pricing_version) == ("manual_adjust", "v3")


def test_save_adds_model(session, repo):
    topup = TokenLedgerTopup(id="tu-9", tenant_id="tenant-a",
                             cycle_year_month="2026-09", amount=100, amount_points=5)
    assert _run(repo.save(topup)) is topup
    (added,) = session.added
    assert isinstance(added, TokenLedgerTopupModel)
    assert (added.tenant_id, added.amount, added.amount_points) == ("tenant-a", 100, 5)
    assert session.commits == 1
