"""SQLAlchemyConfigSnapshotRepository — 內容定址快照與 bot 時間軸（Issue #101）。

timeline_for_bot 以 bot_id 查 trace（不帶 tenant）；歸屬由
config_snapshot_router 先以 GetBotUseCase 驗（見 tenant fence 理由）。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.infrastructure.db.models.config_snapshot_model import ConfigSnapshotModel
from src.infrastructure.db.repositories.config_snapshot_repository import (
    SQLAlchemyConfigSnapshotRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 2, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyConfigSnapshotRepository:
    return SQLAlchemyConfigSnapshotRepository(session)  # type: ignore[arg-type]


def test_ensure_is_insert_on_conflict_do_nothing(session, repo):
    _run(repo.ensure("h1", {"bot_prompt": "p"}, 2))
    sql = session.sql()
    assert "INSERT INTO config_snapshots" in sql
    assert "ON CONFLICT (hash) DO NOTHING" in sql
    params = session.statements[-1].compile().params
    assert params["hash"] == "h1" and params["snapshot_schema"] == 2
    assert session.commits == 1


def test_find_by_hash(session, repo):
    assert _run(repo.find_by_hash("none")) is None
    session.get_result = ConfigSnapshotModel(
        hash="h1", snapshot={"k": 1}, snapshot_schema=2, first_seen_at=T0
    )
    assert _run(repo.find_by_hash("h1")) == {
        "hash": "h1",
        "snapshot": {"k": 1},
        "schema": 2,
        "first_seen_at": T0,
    }


def test_timeline_for_bot_scopes_bot_and_skips_null_hash(session, repo):
    session.queue_result(
        [
            SimpleNamespace(
                config_hash="h1", first_seen_at=T0, last_seen_at=T1, turns=4
            )
        ]
    )
    (item,) = _run(repo.timeline_for_bot("bot-1", limit=7))
    sql = session.sql()
    assert "agent_execution_traces.bot_id = 'bot-1'" in sql
    assert "agent_execution_traces.config_hash IS NOT NULL" in sql
    assert "GROUP BY agent_execution_traces.config_hash" in sql
    assert "LIMIT 7" in sql
    assert item == {"hash": "h1", "first_seen_at": T0, "last_seen_at": T1, "turns": 4}
