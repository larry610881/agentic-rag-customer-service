"""SQLAlchemyProcessingTaskRepository — 查詢條件與實體映射（Issue #101）。

find_by_id 不帶租戶：task_router 以 task.tenant_id 比對呼叫者租戶（映射須保留）。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.knowledge.entity import ProcessingTask
from src.domain.knowledge.value_objects import ProcessingTaskId
from src.infrastructure.db.models.processing_task_model import ProcessingTaskModel
from src.infrastructure.db.repositories.processing_task_repository import (
    SQLAlchemyProcessingTaskRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> ProcessingTaskModel:
    data: dict = {
        "id": "task-1",
        "document_id": "doc-1",
        "tenant_id": "tenant-a",
        "status": "processing",
        "progress": 40,
        "error_message": "",
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return ProcessingTaskModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyProcessingTaskRepository:
    return SQLAlchemyProcessingTaskRepository(session)  # type: ignore[arg-type]


def test_find_by_id_maps_tenant(session, repo):
    assert _run(repo.find_by_id("x")) is None
    session.queue_result([_model()])
    task = _run(repo.find_by_id("task-1"))
    assert "processing_tasks.id = 'task-1'" in session.sql(-1)
    assert task is not None
    assert task.tenant_id == "tenant-a"
    assert (task.document_id, task.status, task.progress) == ("doc-1", "processing", 40)


def test_find_by_document_id_latest(session, repo):
    session.queue_result([_model()])
    task = _run(repo.find_by_document_id("doc-1"))
    sql = session.sql(0)
    assert "processing_tasks.document_id = 'doc-1'" in sql
    assert "ORDER BY processing_tasks.created_at DESC" in sql
    assert "LIMIT 1" in sql
    assert task is not None and task.id.value == "task-1"
    assert _run(repo.find_by_document_id("doc-x")) is None


def test_save_adds_model(session, repo):
    task = ProcessingTask(id=ProcessingTaskId(value="task-9"), document_id="doc-1",
                          tenant_id="tenant-a")
    _run(repo.save(task))
    (added,) = session.added
    assert isinstance(added, ProcessingTaskModel)
    assert (added.id, added.tenant_id) == ("task-9", "tenant-a")
    assert added.status == "pending"
    assert session.commits == 1


def test_update_status_optional_fields(session, repo):
    _run(repo.update_status("task-1", "failed", progress=100, error_message="boom"))
    sql = session.sql(-1)
    assert "processing_tasks.id = 'task-1'" in sql
    assert "status='failed'" in sql
    assert "progress=100" in sql and "error_message='boom'" in sql
    _run(repo.update_status("task-1", "done"))
    sql = session.sql(-1)
    assert "progress" not in sql and "error_message" not in sql
