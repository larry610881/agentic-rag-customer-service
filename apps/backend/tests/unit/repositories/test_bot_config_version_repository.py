"""BotConfigVersion repository — 租戶 scope、樂觀鎖轉移、current 翻轉（Issue #101）。"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timezone

import pytest

from src.domain.prompt_gate.entity import (
    BotConfigVersion,
    InvalidVersionTransitionError,
    VersionConflictError,
)
from src.infrastructure.db.models.bot_config_version_model import (
    BotConfigVersionModel,
)
from src.infrastructure.db.repositories.bot_config_version_repository import (
    SQLAlchemyBotConfigVersionRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
# 單元測試不直接 import sqlalchemy（python-standards 紅線）；只取例外型別
IntegrityError = importlib.import_module("sqlalchemy.exc").IntegrityError


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> BotConfigVersionModel:
    data: dict = {
        "id": "v-1",
        "tenant_id": "tenant-a",
        "bot_id": "bot-1",
        "version_no": 3,
        "config_snapshot": {"bot_prompt": "p"},
        "snapshot_schema": 1,
        "changed_fields": ["bot_prompt"],
        "status": "draft",
        "is_current": False,
        "source": "manual",
        "source_run_id": None,
        "gate_run_id": None,
        "gate_verdict": None,
        "author_user_id": "u-1",
        "published_at": None,
        "created_at": T0,
    }
    data.update(over)
    return BotConfigVersionModel(**data)


def _version(**over) -> BotConfigVersion:
    data: dict = {
        "id": "v-1",
        "tenant_id": "tenant-a",
        "bot_id": "bot-1",
        "version_no": 1,
        "config_snapshot": {"bot_prompt": "p"},
        "status": "published",
        "is_current": True,
        "gate_verdict": "pass",
        "published_at": T0,
    }
    data.update(over)
    return BotConfigVersion(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyBotConfigVersionRepository:
    return SQLAlchemyBotConfigVersionRepository(session)  # type: ignore[arg-type]


def test_find_by_id_requires_tenant_and_maps(session, repo):
    session.queue_result([_model()])
    v = _run(repo.find_by_id("v-1", "tenant-a"))
    sql = session.sql()
    assert "bot_config_versions.id = 'v-1'" in sql
    assert "bot_config_versions.tenant_id = 'tenant-a'" in sql
    assert v is not None
    assert (v.tenant_id, v.bot_id, v.version_no) == ("tenant-a", "bot-1", 3)
    assert v.config_snapshot == {"bot_prompt": "p"}
    assert v.changed_fields == ["bot_prompt"]
    assert _run(repo.find_by_id("v-x", "tenant-b")) is None


def test_find_and_count_by_bot_scope_bot_tenant_status(session, repo):
    session.queue_result([_model(), _model(id="v-2", version_no=2)])
    vs = _run(
        repo.find_by_bot("bot-1", "tenant-a", status="draft", limit=5, offset=10)
    )
    sql = session.sql()
    for cond in (
        "bot_config_versions.bot_id = 'bot-1'",
        "bot_config_versions.tenant_id = 'tenant-a'",
        "bot_config_versions.status = 'draft'",
    ):
        assert cond in sql
    assert "LIMIT 5" in sql and "OFFSET 10" in sql
    assert [v.id for v in vs] == ["v-1", "v-2"]

    session.queue_result([7])
    assert _run(repo.count_by_bot("bot-1", "tenant-a")) == 7
    sql = session.sql()
    assert "bot_config_versions.tenant_id = 'tenant-a'" in sql
    assert "status =" not in sql


def test_find_current_and_next_version_no_scope_bot(session, repo):
    session.queue_result([_model(is_current=True)])
    cur = _run(repo.find_current("bot-1"))
    assert "bot_config_versions.bot_id = 'bot-1'" in session.sql()
    assert "is_current IS true" in session.sql()
    assert cur is not None and cur.is_current
    assert _run(repo.find_current("bot-2")) is None

    session.queue_result([4])
    assert _run(repo.next_version_no("bot-1")) == 5
    assert "max(bot_config_versions.version_no)" in session.sql()


def test_save_new_adds_model(session, repo):
    _run(repo.save(_version()))
    (m,) = session.added
    assert (m.tenant_id, m.bot_id, m.status) == ("tenant-a", "bot-1", "published")
    assert session.commits == 1


def test_save_existing_only_mutates_state_machine_fields(session, repo):
    existing = _model()
    session.get_result = existing
    _run(repo.save(_version(config_snapshot={"bot_prompt": "竄改"})))
    assert session.added == []
    assert existing.status == "published"
    assert existing.is_current is True
    assert existing.gate_verdict == "pass"
    # append-only：快照內容不可被覆寫
    assert existing.config_snapshot == {"bot_prompt": "p"}


def test_status_transition_is_conditional_on_expected_status(session, repo):
    session.queue_result(rowcount=1)
    _run(
        repo.save_status_transition(
            _version(), expected_status="validating", action="x"
        )
    )
    sql = session.sql()
    assert "UPDATE bot_config_versions" in sql
    assert "bot_config_versions.status = 'validating'" in sql


def test_status_transition_lost_update_raises_with_actual_status(session, repo):
    session.queue_result(rowcount=0)
    session.get_result = _model(status="rejected")
    with pytest.raises(InvalidVersionTransitionError) as exc:
        _run(
            repo.save_status_transition(
                _version(), expected_status="validating", action="publish"
            )
        )
    assert "rejected" in str(exc.value)


def test_create_next_version_retries_on_unique_conflict(session, repo):
    fails = {"n": 1}
    real_commit = session.commit

    async def flaky_commit():
        if fails["n"]:
            fails["n"] -= 1
            raise IntegrityError("insert", {}, Exception("uq_bcv_bot_version"))
        await real_commit()

    session.commit = flaky_commit  # type: ignore[method-assign]
    session.queue_result([1])  # 第一次取號 → 2（撞號）
    session.queue_result([2])  # 重取號 → 3

    v = _run(repo.create_next_version(_version()))

    assert v.version_no == 3
    assert len(session.added) == 2


def test_create_next_version_gives_up_after_retries(session, repo):
    async def always_conflict():
        raise IntegrityError("insert", {}, Exception("dup"))

    session.commit = always_conflict  # type: ignore[method-assign]
    with pytest.raises(VersionConflictError):
        _run(repo.create_next_version(_version()))
    assert len(session.added) == 5


def test_revert_validating_to_draft(session, repo):
    assert _run(repo.revert_validating_to_draft([])) == 0
    assert session.statements == []

    session.queue_result(rowcount=2)
    assert _run(repo.revert_validating_to_draft(["v-1", "v-2"])) == 2
    sql = session.sql()
    assert "bot_config_versions.id IN ('v-1', 'v-2')" in sql
    assert "bot_config_versions.status = 'validating'" in sql


def test_revert_stale_validating_excludes_active_runs(session, repo):
    session.queue_result(rowcount=3)
    assert _run(repo.revert_stale_validating_versions()) == 3
    sql = session.sql()
    assert "gate_run_id IS NULL" in sql
    assert "NOT IN (SELECT prompt_gate_runs.id" in sql
    assert "'queued', 'running'" in sql


def test_set_current_clears_others_then_sets(session, repo):
    _run(repo.set_current("bot-1", "v-9"))
    clear, set_ = session.all_sql()
    assert "bot_config_versions.bot_id = 'bot-1'" in clear
    assert "bot_config_versions.id != 'v-9'" in clear
    assert "is_current=false" in clear.replace(" ", "")
    assert "bot_config_versions.id = 'v-9'" in set_
    assert "is_current=true" in set_.replace(" ", "")
