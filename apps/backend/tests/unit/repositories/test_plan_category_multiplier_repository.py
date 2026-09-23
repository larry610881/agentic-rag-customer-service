"""SQLAlchemyPlanCategoryMultiplierRepository — 方案分類倍率（Issue #101）。"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from src.domain.plan.value_objects import PlanCategoryMultiplier
from src.infrastructure.db.models.plan_category_multiplier_model import (
    PlanCategoryMultiplierModel,
)
from src.infrastructure.db.repositories.plan_category_multiplier_repository import (
    SQLAlchemyPlanCategoryMultiplierRepository,
)
from tests.unit.repositories.spy_session import SpySession


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyPlanCategoryMultiplierRepository:
    return SQLAlchemyPlanCategoryMultiplierRepository(session)  # type: ignore[arg-type]


def test_list_for_plan_scopes_plan_and_maps_decimal(session, repo):
    session.queue_result(
        [
            PlanCategoryMultiplierModel(
                plan_id="p-1", usage_category="chat_web", multiplier="1.5"
            )
        ]
    )
    (m,) = _run(repo.list_for_plan("p-1"))
    assert "plan_category_multipliers.plan_id = 'p-1'" in session.sql()
    assert m.multiplier == Decimal("1.5") and isinstance(m.multiplier, Decimal)
    assert m.usage_category == "chat_web"


def test_replace_for_plan_deletes_then_adds(session, repo):
    _run(
        repo.replace_for_plan(
            "p-1",
            [
                PlanCategoryMultiplier(
                    plan_id="ignored", usage_category="line", multiplier=Decimal("2")
                ),
                PlanCategoryMultiplier(
                    plan_id="ignored", usage_category="rag", multiplier=Decimal("0.5")
                ),
            ],
        )
    )
    assert "DELETE FROM plan_category_multipliers" in session.sql()
    assert "plan_category_multipliers.plan_id = 'p-1'" in session.sql()
    # 一律寫入目標方案 id，不採用傳入值
    assert [(m.plan_id, m.usage_category) for m in session.added] == [
        ("p-1", "line"),
        ("p-1", "rag"),
    ]
    assert session.commits == 1
