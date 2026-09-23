"""SQLAlchemyOptimizationRunRepository — 租戶過濾（含 raw SQL）與映射（Issue #101）。

get_iterations(run_id) 不帶租戶：所有呼叫端（GetRun / Apply / Report / Diff）
都經 _check_run_tenant 比對 iterations 的 tenant_id。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.domain.eval_dataset.run_entity import OptimizationIteration
from src.infrastructure.db.models.prompt_opt_run_model import PromptOptRunModel
from src.infrastructure.db.repositories.optimization_run_repository import (
    SQLAlchemyOptimizationRunRepository,
)
from tests.unit.repositories.spy_session import FakeResult, SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


class _ParamSpySession(SpySession):
    """另記錄 execute 的綁定參數（text() 查詢的租戶值在參數裡）。"""

    def __init__(self) -> None:
        super().__init__()
        self.params: list[Any] = []

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> FakeResult:
        self.params.append(args[0] if args else None)
        return await super().execute(stmt)


def _model(**over) -> PromptOptRunModel:
    data: dict = {
        "id": "it-1",
        "run_id": "run-1",
        "iteration": 1,
        "tenant_id": "tenant-a",
        "target_field": "bot_prompt",
        "bot_id": "bot-1",
        "prompt_snapshot": "你是客服",
        "score": 0.9,
        "passed_count": 9,
        "total_count": 10,
        "is_best": True,
        "details": {"type": "optimization"},
        "created_at": T0,
    }
    data.update(over)
    return PromptOptRunModel(**data)


@pytest.fixture
def session() -> _ParamSpySession:
    return _ParamSpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyOptimizationRunRepository:
    return SQLAlchemyOptimizationRunRepository(session)  # type: ignore[arg-type]


def test_get_iterations_scoped_to_run_and_maps_tenant(session, repo):
    session.queue_result([_model()])
    (it,) = _run(repo.get_iterations("run-1"))
    assert "prompt_opt_runs.run_id = 'run-1'" in session.sql(0)
    # 呼叫端靠 tenant_id 做擁有權檢查 → 映射必須保留
    assert it.tenant_id == "tenant-a"
    assert (it.id, it.iteration, it.score, it.is_best) == ("it-1", 1, 0.9, True)
    assert it.details == {"type": "optimization"}


def test_get_best_iteration(session, repo):
    assert _run(repo.get_best_iteration("run-1")) is None
    sql = session.sql(0)
    assert "prompt_opt_runs.run_id = 'run-1'" in sql
    assert "prompt_opt_runs.is_best IS true" in sql
    session.queue_result([_model()])
    best = _run(repo.get_best_iteration("run-1"))
    assert best is not None and best.prompt_snapshot == "你是客服"


def test_list_runs_with_tenant_binds_tenant_param(session, repo):
    row = SimpleNamespace(_mapping={"run_id": "run-1", "tenant_id": "tenant-a"})
    session.queue_result([row])
    out = _run(repo.list_runs("tenant-a", limit=5, offset=10))
    sql = session.sql(0)
    assert "WHERE tenant_id = :tenant_id" in str(session.statements[0])
    assert "FROM prompt_opt_runs" in sql
    assert session.params[0] == {"limit": 5, "offset": 10, "tenant_id": "tenant-a"}
    assert out == [{"run_id": "run-1", "tenant_id": "tenant-a"}]


def test_list_runs_admin_without_tenant(session, repo):
    _run(repo.list_runs(None))
    assert "WHERE" not in str(session.statements[0])
    assert "tenant_id" not in session.params[0]


def test_count_runs(session, repo):
    session.queue_result([3])
    assert _run(repo.count_runs("tenant-a")) == 3
    assert "WHERE tenant_id = :tenant_id" in str(session.statements[0])
    assert session.params[0] == {"tenant_id": "tenant-a"}
    assert _run(repo.count_runs()) == 0
    assert "WHERE" not in str(session.statements[-1])


def test_save_iteration_adds_model_with_generated_id(session, repo):
    it = OptimizationIteration(run_id="run-1", iteration=0, tenant_id="tenant-a",
                               target_field="bot_prompt", score=0.5)
    _run(repo.save_iteration(it))
    (added,) = session.added
    assert isinstance(added, PromptOptRunModel)
    assert added.tenant_id == "tenant-a"
    assert added.run_id == "run-1"
    assert len(added.id) == 36
