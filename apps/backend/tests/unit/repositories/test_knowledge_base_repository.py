"""SQLAlchemyKnowledgeBaseRepository — 租戶過濾條件與實體映射（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel
from src.infrastructure.db.repositories.knowledge_base_repository import (
    SQLAlchemyKnowledgeBaseRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> KnowledgeBaseModel:
    data: dict = {
        "id": "kb-1",
        "tenant_id": "tenant-a",
        "name": "FAQ",
        "description": "常見問題",
        "kb_type": "user",
        "ocr_mode": "catalog",
        "ocr_model": "m-ocr",
        "context_model": "m-ctx",
        "classification_model": "m-cls",
        "chunk_strategy": "recursive",
        "ocr_slice_grid": None,
        "dm_metadata_model": None,
        "dm_metadata": None,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return KnowledgeBaseModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyKnowledgeBaseRepository:
    return SQLAlchemyKnowledgeBaseRepository(session)  # type: ignore[arg-type]


def test_find_by_id_maps_entity_with_document_count(session, repo):
    session.queue_result([(_model(), 7)])

    kb = _run(repo.find_by_id("kb-1"))

    sql = session.sql(0)
    assert "knowledge_bases.id = 'kb-1'" in sql
    # 文件數只算 top-level
    assert "documents.parent_id IS NULL" in sql
    assert kb is not None
    assert kb.id.value == "kb-1"
    assert kb.tenant_id == "tenant-a"
    assert kb.document_count == 7
    assert kb.ocr_mode == "catalog"
    assert kb.chunk_strategy == "recursive"
    assert kb.ocr_slice_grid == "" and kb.dm_metadata_model == ""
    assert kb.dm_metadata == {}


def test_find_by_id_missing(repo):
    assert _run(repo.find_by_id("nope")) is None


def test_find_all_by_tenant_filters_tenant_and_user_type(session, repo):
    session.queue_result([(_model(dm_metadata={"merchant": "X"}), 0)])
    (kb,) = _run(repo.find_all_by_tenant("tenant-a", limit=10, offset=20))
    sql = session.sql(0)
    assert "knowledge_bases.tenant_id = 'tenant-a'" in sql
    assert "knowledge_bases.kb_type = 'user'" in sql
    assert "LIMIT 10" in sql and "OFFSET 20" in sql
    assert kb.dm_metadata == {"merchant": "X"}


def test_find_all_with_tenant_filter(session, repo):
    _run(repo.find_all(tenant_id="tenant-a", limit=5, offset=0))
    sql = session.sql(0)
    assert "knowledge_bases.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 5" in sql


def test_find_all_without_tenant_is_admin_listing(session, repo):
    # 只有 system_admin 端點（ListAllKnowledgeBasesUseCase）會不帶 tenant_id
    _run(repo.find_all())
    assert "knowledge_bases.tenant_id =" not in session.sql(0)


def test_count_by_tenant(session, repo):
    session.queue_result([3])
    assert _run(repo.count_by_tenant("tenant-a")) == 3
    sql = session.sql(0)
    assert "knowledge_bases.tenant_id = 'tenant-a'" in sql
    assert "knowledge_bases.kb_type = 'user'" in sql


def test_count_all_optional_tenant(session, repo):
    session.queue_result([2])
    assert _run(repo.count_all(tenant_id="tenant-a")) == 2
    assert "knowledge_bases.tenant_id = 'tenant-a'" in session.sql(0)
    _run(repo.count_all())
    assert "WHERE" not in session.sql(-1)


def test_find_system_kbs_filters_tenant_and_system_type(session, repo):
    session.queue_result([(_model(kb_type="system"), 1)])
    (kb,) = _run(repo.find_system_kbs("tenant-a"))
    sql = session.sql(0)
    assert "knowledge_bases.tenant_id = 'tenant-a'" in sql
    assert "knowledge_bases.kb_type = 'system'" in sql
    assert kb.kb_type == "system"


def test_save_adds_model(session, repo):
    kb = KnowledgeBase(id=KnowledgeBaseId(value="kb-9"), tenant_id="tenant-a",
                       name="n", dm_metadata={})
    _run(repo.save(kb))
    (added,) = session.added
    assert isinstance(added, KnowledgeBaseModel)
    assert (added.id, added.tenant_id, added.name) == ("kb-9", "tenant-a", "n")
    assert session.commits == 1


def test_update_only_whitelisted_non_null_fields(session, repo):
    _run(repo.update("kb-1", name="新名", tenant_id="tenant-b", description=None))
    sql = session.sql(0)
    assert "knowledge_bases.id = 'kb-1'" in sql
    assert "name='新名'" in sql
    # tenant_id 不在白名單，不能藉 update 搬家到他租戶
    assert "tenant_id" not in sql
    assert "description" not in sql


def test_update_with_nothing_allowed_is_noop(session, repo):
    _run(repo.update("kb-1", tenant_id="tenant-b"))
    assert session.statements == []


def test_delete_cascades_chunks_documents_kb(session, repo):
    session.queue_result([("d1",), ("d2",)])
    _run(repo.delete("kb-1"))
    select_sql, chunks_sql, docs_sql, kb_sql = session.all_sql()
    assert "documents.kb_id = 'kb-1'" in select_sql
    assert chunks_sql.startswith("DELETE FROM chunks")
    assert "chunks.document_id IN ('d1', 'd2')" in chunks_sql
    assert docs_sql.startswith("DELETE FROM documents")
    assert "documents.kb_id = 'kb-1'" in docs_sql
    assert "knowledge_bases.id = 'kb-1'" in kb_sql


def test_delete_without_documents_skips_chunk_delete(session, repo):
    _run(repo.delete("kb-1"))
    assert len(session.statements) == 3
    assert not any(s.startswith("DELETE FROM chunks") for s in session.all_sql())
