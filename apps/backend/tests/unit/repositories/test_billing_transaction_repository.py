"""SQLAlchemyBillingTransactionRepository — 租戶過濾條件與聚合映射（Issue #101）。"""

from __future__ import annotations

import asyncio
from collections import namedtuple
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.domain.billing.entity import BillingTransaction
from src.infrastructure.db.models.billing_transaction_model import (
    BillingTransactionModel,
)
from src.infrastructure.db.repositories.billing_transaction_repository import (
    SQLAlchemyBillingTransactionRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> BillingTransactionModel:
    data: dict = {
        "id": "tx-1",
        "tenant_id": "tenant-a",
        "ledger_id": "led-1",
        "cycle_year_month": "2026-09",
        "plan_name": "pro",
        "transaction_type": "auto_topup",
        "addon_tokens_added": 1000,
        "amount_currency": "TWD",
        "amount_value": Decimal("99.00"),
        "triggered_by": "system",
        "reason": None,
        "created_at": T0,
    }
    data.update(over)
    return BillingTransactionModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyBillingTransactionRepository:
    return SQLAlchemyBillingTransactionRepository(session)  # type: ignore[arg-type]


def test_find_by_tenant_and_cycle_filters_and_maps(session, repo):
    session.queue_result([_model()])
    (tx,) = _run(repo.find_by_tenant_and_cycle("tenant-a", "2026-09"))
    sql = session.sql(0)
    assert "billing_transactions.tenant_id = 'tenant-a'" in sql
    assert "billing_transactions.cycle_year_month = '2026-09'" in sql
    assert tx.id == "tx-1" and tx.tenant_id == "tenant-a"
    assert tx.amount_value == Decimal("99.00")
    assert tx.addon_tokens_added == 1000
    assert tx.reason == ""


def test_list_recent_with_tenant(session, repo):
    _run(repo.list_recent(limit=10, offset=5, tenant_id="tenant-a"))
    sql = session.sql(0)
    assert "billing_transactions.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 10" in sql and "OFFSET 5" in sql


def test_list_recent_without_tenant_is_admin_listing(session, repo):
    # 只有 system_admin 的 quota events 端點不帶 tenant_id
    _run(repo.list_recent())
    assert "WHERE" not in session.sql(0)


def test_count_recent(session, repo):
    session.queue_result([3])
    assert _run(repo.count_recent("tenant-a")) == 3
    assert "billing_transactions.tenant_id = 'tenant-a'" in session.sql(0)
    assert _run(repo.count_recent()) == 0
    assert "WHERE" not in session.sql(-1)


def test_aggregate_monthly_revenue_with_tenant(session, repo):
    Row = namedtuple("Row", "cycle total cnt tokens")
    session.queue_result(
        [Row("2026-08", Decimal("10"), 2, 500), Row("2026-09", None, None, None)]
    )
    points = _run(repo.aggregate_monthly_revenue(
        start_cycle="2026-08", end_cycle="2026-09", tenant_id="tenant-a"))
    sql = session.sql(0)
    assert "billing_transactions.tenant_id = 'tenant-a'" in sql
    assert "billing_transactions.cycle_year_month >= '2026-08'" in sql
    assert points[0].total_amount == Decimal("10")
    assert points[0].transaction_count == 2
    assert points[0].addon_tokens_total == 500
    assert points[1].total_amount == Decimal("0")
    assert points[1].transaction_count == 0


def test_aggregate_by_plan_and_top_tenants(session, repo):
    Plan = namedtuple("Plan", "plan total cnt")
    Ten = namedtuple("Ten", "tid total cnt")
    session.queue_result([Plan("pro", Decimal("5"), 1)])
    session.queue_result([Ten("tenant-a", None, 3)])
    (plan,) = _run(repo.aggregate_by_plan(start_cycle="2026-01", end_cycle="2026-09"))
    (ten,) = _run(repo.aggregate_top_tenants(start_cycle="2026-01",
                                             end_cycle="2026-09", limit=3))
    assert (plan.plan_name, plan.total_amount, plan.transaction_count) == (
        "pro", Decimal("5"), 1)
    assert (ten.tenant_id, ten.total_amount, ten.transaction_count) == (
        "tenant-a", Decimal("0"), 3)
    assert "LIMIT 3" in session.sql(-1)


def test_save_adds_model(session, repo):
    tx = BillingTransaction(id="tx-9", tenant_id="tenant-a", ledger_id="led-1",
                            cycle_year_month="2026-09", reason="")
    assert _run(repo.save(tx)) is tx
    (added,) = session.added
    assert isinstance(added, BillingTransactionModel)
    assert (added.id, added.tenant_id) == ("tx-9", "tenant-a")
    assert added.reason is None
    assert session.commits == 1
