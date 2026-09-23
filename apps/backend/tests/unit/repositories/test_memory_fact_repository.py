"""SQLAlchemyMemoryFactRepository — profile 範圍查詢、過期過濾與 upsert（Issue #101）。

memory_facts 以 profile_id 查詢；profile 由 ResolveIdentityUseCase 以
(tenant_id, source, external_id) 解析，不接受外部傳入（見 tenant fence 理由）。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.memory.entity import MemoryFact
from src.domain.memory.value_objects import MemoryFactId
from src.infrastructure.db.models.memory_fact_model import MemoryFactModel
from src.infrastructure.db.repositories.memory_fact_repository import (
    SQLAlchemyMemoryFactRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> MemoryFactModel:
    data: dict = {
        "id": "f-1",
        "profile_id": "p-1",
        "tenant_id": "tenant-a",
        "memory_type": "long_term",
        "category": "preference",
        "key": "size",
        "value": "M",
        "source_conversation_id": "c-1",
        "confidence": 0.9,
        "last_accessed_at": None,
        "expires_at": None,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return MemoryFactModel(**data)


def _fact(**over) -> MemoryFact:
    data: dict = {
        "id": MemoryFactId(value="f-new"),
        "profile_id": "p-1",
        "tenant_id": "tenant-a",
        "key": "size",
        "value": "L",
        "category": "preference",
        "confidence": 0.7,
    }
    data.update(over)
    return MemoryFact(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyMemoryFactRepository:
    return SQLAlchemyMemoryFactRepository(session)  # type: ignore[arg-type]


def test_find_by_profile_excludes_expired_by_default(session, repo):
    session.queue_result([_model()])
    (f,) = _run(repo.find_by_profile("p-1", memory_type="long_term"))
    sql = session.sql()
    assert "memory_facts.profile_id = 'p-1'" in sql
    assert "memory_facts.memory_type = 'long_term'" in sql
    assert "memory_facts.expires_at IS NULL OR memory_facts.expires_at >" in sql
    assert (f.tenant_id, f.key, f.value, f.confidence) == ("tenant-a", "size", "M", 0.9)


def test_find_by_profile_include_expired(session, repo):
    _run(repo.find_by_profile("p-1", include_expired=True))
    sql = session.sql()
    assert "expires_at" not in sql.split("WHERE")[1]
    assert "memory_type =" not in sql


def test_save_merges_with_tenant(session, repo):
    _run(repo.save(_fact()))
    (m,) = session.merged
    assert (m.id, m.tenant_id, m.profile_id) == ("f-new", "tenant-a", "p-1")


def test_upsert_by_key_updates_existing(session, repo):
    existing = _model()
    session.queue_result([existing])
    _run(repo.upsert_by_key(_fact()))
    sql = session.sql()
    assert "memory_facts.profile_id = 'p-1'" in sql
    assert "memory_facts.key = 'size'" in sql
    assert (existing.value, existing.confidence) == ("L", 0.7)
    assert existing.id == "f-1"  # 保留原列
    assert existing.updated_at > T0
    assert session.added == []


def test_upsert_by_key_inserts_when_missing(session, repo):
    _run(repo.upsert_by_key(_fact()))
    (m,) = session.added
    assert (m.id, m.tenant_id, m.value) == ("f-new", "tenant-a", "L")


def test_delete(session, repo):
    _run(repo.delete("f-1"))
    assert "DELETE FROM memory_facts WHERE memory_facts.id = 'f-1'" in session.sql()
