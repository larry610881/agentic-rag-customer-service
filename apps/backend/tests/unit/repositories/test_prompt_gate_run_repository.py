"""SQLAlchemyPromptGateRunRepository — 租戶 scope、每日計數與孤兒清理（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.prompt_gate.gate_run_entity import PromptGateRun
from src.infrastructure.db.models.prompt_gate_run_model import PromptGateRunModel
from src.infrastructure.db.repositories.prompt_gate_run_repository import (
    SQLAlchemyPromptGateRunRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> PromptGateRunModel:
    data: dict = {
        "id": "run-1",
        "tenant_id": "tenant-a",
        "bot_id": "bot-1",
        "version_id": "v-1",
        "status": "completed",
        "verdict": "pass",
        "fail_reasons": None,
        "dataset_ids": ["ds-1"],
        "repeats": 2,
        "soft_threshold": 0.8,
        "total_cases": 10,
        "hard_failed_cases": 0,
        "soft_pass_rate": 0.9,
        "unstable_cases": 1,
        "est_cost": 0.5,
        "actual_cost": 0.4,
        "input_tokens": 100,
        "output_tokens": 50,
        "details": {"k": "v"},
        "error_message": None,
        "triggered_by": "u-1",
        "created_at": T0,
        "started_at": T0,
        "completed_at": T0,
    }
    data.update(over)
    return PromptGateRunModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyPromptGateRunRepository:
    return SQLAlchemyPromptGateRunRepository(session)  # type: ignore[arg-type]


def test_find_by_id_requires_tenant(session, repo):
    session.queue_result([_model()])
    run = _run(repo.find_by_id("run-1", "tenant-a"))
    sql = session.sql()
    assert "prompt_gate_runs.id = 'run-1'" in sql
    assert "prompt_gate_runs.tenant_id = 'tenant-a'" in sql
    assert run is not None
    assert run.fail_reasons == [] and run.dataset_ids == ["ds-1"]
    assert (run.verdict, run.soft_pass_rate) == ("pass", 0.9)
    assert _run(repo.find_by_id("run-1", "tenant-b")) is None


def test_count_today_scopes_bot_and_day(session, repo):
    session.queue_result([3])
    assert _run(repo.count_today("bot-1")) == 3
    sql = session.sql()
    assert "prompt_gate_runs.bot_id = 'bot-1'" in sql
    today = datetime.now(timezone.utc).date().isoformat()
    assert f"prompt_gate_runs.created_at >= '{today} 00:00:00" in sql


def test_save_new_and_update_copy_all_fields(session, repo):
    run = PromptGateRun(
        id="run-9", tenant_id="tenant-a", bot_id="bot-1", version_id="v-1"
    )
    _run(repo.save(run))
    (m,) = session.added
    assert (m.id, m.tenant_id, m.version_id) == ("run-9", "tenant-a", "v-1")

    existing = _model(status="running", verdict=None)
    session.get_result = existing
    run.id = "run-1"
    run.status = "completed"
    run.verdict = "fail"
    run.fail_reasons = ["hard_fail"]
    _run(repo.save(run))
    assert (existing.status, existing.verdict) == ("completed", "fail")
    assert existing.fail_reasons == ["hard_fail"]


def test_mark_orphans_error_only_old_queued_or_running(session, repo):
    assert _run(repo.mark_orphans_error()) == []
    assert len(session.statements) == 1  # 沒有孤兒 → 不更新

    session.queue_result(["v-1", "v-2"])
    assert _run(repo.mark_orphans_error(grace_minutes=30)) == ["v-1", "v-2"]
    select_sql, update_sql = session.all_sql()[1:]
    for sql in (select_sql, update_sql):
        assert "prompt_gate_runs.status IN ('queued', 'running')" in sql
        assert "prompt_gate_runs.created_at <" in sql
    assert "status='error'" in update_sql.replace(" ", "")
