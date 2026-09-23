"""SQLAlchemyEvalDatasetRepository — 租戶過濾條件與實體映射（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.eval_dataset.entity import EvalDataset, EvalTestCase
from src.domain.eval_dataset.value_objects import EvalDatasetId, EvalTestCaseId
from src.infrastructure.db.models.eval_dataset_model import (
    EvalDatasetModel,
    EvalTestCaseModel,
)
from src.infrastructure.db.repositories.eval_dataset_repository import (
    SQLAlchemyEvalDatasetRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> EvalDatasetModel:
    data: dict = {
        "id": "ds-1",
        "tenant_id": "tenant-a",
        "bot_id": "bot-1",
        "name": "回歸集",
        "description": None,
        "target_prompt": "bot_prompt",
        "default_assertions": None,
        "cost_config": {"max_calls": 3},
        "include_security": True,
        "is_platform_base": False,
        "created_at": T0,
        "updated_at": T0,
        "test_cases": [
            EvalTestCaseModel(
                id="tc-1", dataset_id="ds-1", case_id="C1", question="運費?",
                priority="P0", category=None, conversation_history=None,
                assertions=[{"type": "contains", "value": "免運"}], tags=None,
                enabled=False, created_at=T0,
            )
        ],
    }
    data.update(over)
    return EvalDatasetModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyEvalDatasetRepository:
    return SQLAlchemyEvalDatasetRepository(session)  # type: ignore[arg-type]


def test_find_by_id_maps_dataset_and_cases(session, repo):
    session.queue_result([_model()])
    ds = _run(repo.find_by_id("ds-1"))
    assert "eval_datasets.id = 'ds-1'" in session.sql(0)
    assert ds is not None
    assert ds.id.value == "ds-1"
    assert ds.tenant_id == "tenant-a"
    assert ds.description == ""
    assert ds.default_assertions == []
    assert ds.cost_config == {"max_calls": 3}
    (tc,) = ds.test_cases
    assert tc.id.value == "tc-1"
    assert tc.priority == "P0"
    assert tc.category == ""
    assert tc.conversation_history == [] and tc.tags == []
    assert tc.assertions == [{"type": "contains", "value": "免運"}]
    assert tc.enabled is False


def test_find_by_id_missing(repo):
    assert _run(repo.find_by_id("x")) is None


def test_find_all_by_tenant_filters_tenant(session, repo):
    session.queue_result([_model(test_cases=[])])
    (ds,) = _run(repo.find_all_by_tenant("tenant-a", limit=5, offset=10))
    sql = session.sql(0)
    assert "eval_datasets.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 5" in sql and "OFFSET 10" in sql
    assert ds.test_cases == []


def test_find_by_bot_filters_bot_and_tenant(session, repo):
    _run(repo.find_by_bot("bot-1", "tenant-a"))
    sql = session.sql(0)
    assert "eval_datasets.bot_id = 'bot-1'" in sql
    assert "eval_datasets.tenant_id = 'tenant-a'" in sql


def test_find_platform_base(session, repo):
    session.queue_result([_model(is_platform_base=True)])
    (ds,) = _run(repo.find_platform_base())
    assert "eval_datasets.is_platform_base IS true" in session.sql(0)
    assert ds.is_platform_base is True


def test_find_all_is_unscoped_admin_listing(session, repo):
    # ListEvalDatasetsUseCase 只在 system_admin（tenant_id=None）時走這裡
    _run(repo.find_all(limit=3, offset=6))
    sql = session.sql(0)
    assert "WHERE" not in sql
    assert "LIMIT 3" in sql and "OFFSET 6" in sql


def test_count_by_tenant_and_count_all(session, repo):
    session.queue_result([4])
    assert _run(repo.count_by_tenant("tenant-a")) == 4
    assert "eval_datasets.tenant_id = 'tenant-a'" in session.sql(0)
    session.queue_result([9])
    assert _run(repo.count_all()) == 9
    assert "WHERE" not in session.sql(-1)


def test_save_merges_model(session, repo):
    ds = EvalDataset(id=EvalDatasetId(value="ds-9"), tenant_id="tenant-a",
                     bot_id="bot-1", name="n")
    _run(repo.save(ds))
    (merged,) = session.merged
    assert isinstance(merged, EvalDatasetModel)
    assert (merged.id, merged.tenant_id, merged.bot_id) == ("ds-9", "tenant-a", "bot-1")
    assert session.commits == 1


def test_save_test_case_merges_model(session, repo):
    tc = EvalTestCase(id=EvalTestCaseId(value="tc-9"), dataset_id="ds-1",
                      case_id="C9", question="q", assertions=[{"t": 1}])
    _run(repo.save_test_case(tc))
    (merged,) = session.merged
    assert isinstance(merged, EvalTestCaseModel)
    assert (merged.id, merged.dataset_id) == ("tc-9", "ds-1")


def test_delete_and_delete_test_case(session, repo):
    _run(repo.delete("ds-1"))
    _run(repo.delete_test_case("tc-1"))
    ds_sql, tc_sql = session.all_sql()
    assert ds_sql.startswith("DELETE FROM eval_datasets")
    assert "eval_datasets.id = 'ds-1'" in ds_sql
    assert tc_sql.startswith("DELETE FROM eval_test_cases")
    assert "eval_test_cases.id = 'tc-1'" in tc_sql
