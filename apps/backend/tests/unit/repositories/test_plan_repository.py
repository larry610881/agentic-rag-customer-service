"""SQLAlchemyPlanRepository — 全域方案表（無租戶欄位）的查詢與寫入（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.domain.plan.entity import Plan
from src.infrastructure.db.models.plan_model import PlanModel
from src.infrastructure.db.repositories.plan_repository import (
    SQLAlchemyPlanRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> PlanModel:
    data: dict = {
        "id": "p-1",
        "name": "pro",
        "base_monthly_tokens": 1000,
        "addon_pack_tokens": 100,
        "base_price": Decimal("990"),
        "addon_price": Decimal("99"),
        "currency": "TWD",
        "description": "專業版",
        "is_active": True,
        "billing_mode": "points",
        "monthly_points": 5000,
        "addon_pack_points": 500,
        "default_category_multiplier": Decimal("1.5"),
        "exhaustion_policy": "block",
        "tenant_may_change_policy": True,
        "auto_topup_monthly_cap": 3,
        "grace_percent": 10,
        "block_message": "額度用完",
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return PlanModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyPlanRepository:
    return SQLAlchemyPlanRepository(session)  # type: ignore[arg-type]


def test_find_by_id_maps_billing_fields(session, repo):
    session.get_result = _model()
    p = _run(repo.find_by_id("p-1"))
    assert p is not None
    assert (p.name, p.billing_mode, p.monthly_points) == ("pro", "points", 5000)
    assert p.default_category_multiplier == Decimal("1.5")
    assert (p.exhaustion_policy, p.grace_percent) == ("block", 10)
    session.get_result = None
    assert _run(repo.find_by_id("x")) is None


def test_find_by_name(session, repo):
    session.queue_result([_model()])
    assert _run(repo.find_by_name("pro")).id == "p-1"
    assert "plans.name = 'pro'" in session.sql()
    assert _run(repo.find_by_name("none")) is None


def test_find_all_optionally_hides_inactive(session, repo):
    session.queue_result([_model()])
    assert len(_run(repo.find_all())) == 1
    assert "is_active" not in session.sql().split("FROM plans")[1]

    _run(repo.find_all(include_inactive=False))
    assert "plans.is_active IS true" in session.sql()


def test_save_new_and_update(session, repo):
    plan = Plan(id="p-2", name="basic", monthly_points=10, block_message="停")
    assert _run(repo.save(plan)) is plan
    (m,) = session.added
    assert (m.name, m.monthly_points, m.block_message) == ("basic", 10, "停")

    existing = _model()
    session.get_result = existing
    _run(repo.save(Plan(id="p-1", name="pro", monthly_points=9, grace_percent=0)))
    assert existing.monthly_points == 9 and existing.grace_percent == 0
    assert existing.updated_at > T0


def test_delete_and_count_tenants_using_plan(session, repo):
    _run(repo.delete("p-1"))
    assert "DELETE FROM plans WHERE plans.id = 'p-1'" in session.sql()

    session.queue_result([2])
    assert _run(repo.count_tenants_using_plan("pro")) == 2
    assert "tenants.plan = 'pro'" in session.sql()
