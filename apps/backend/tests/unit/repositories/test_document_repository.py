"""SQLAlchemyDocumentRepository — 查詢範圍條件與實體映射（Issue #101）。

documents / chunks 的列表查詢以 kb_id（父範圍）或 document_id 為界；
kb 的擁有權由呼叫端（ensure_kb_accessible 等）檢查，這裡守「範圍條件一定在」。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.knowledge.entity import Chunk, Document
from src.domain.knowledge.value_objects import ChunkId, DocumentId
from src.infrastructure.db.models.chunk_model import ChunkModel
from src.infrastructure.db.models.document_model import DocumentModel
from src.infrastructure.db.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _doc_model(**over) -> DocumentModel:
    data: dict = {
        "id": "doc-1",
        "kb_id": "kb-1",
        "tenant_id": "tenant-a",
        "filename": "faq.pdf",
        "content_type": "application/pdf",
        "content": "內容",
        "status": "processed",
        "parent_id": None,
        "page_number": None,
        "chunk_count": 3,
        "avg_chunk_length": 100,
        "min_chunk_length": 50,
        "max_chunk_length": 150,
        "quality_score": 0.8,
        "quality_issues": "too_short,duplicate",
        "source": None,
        "source_id": None,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return DocumentModel(**data)


def _chunk_model(**over) -> ChunkModel:
    data: dict = {
        "id": "c-1",
        "document_id": "doc-1",
        "tenant_id": "tenant-a",
        "content": "chunk",
        "context_text": None,
        "chunk_index": 2,
        "metadata_": None,
        "category_id": "cat-1",
        "quality_flag": "low",
    }
    data.update(over)
    return ChunkModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyDocumentRepository:
    return SQLAlchemyDocumentRepository(session)  # type: ignore[arg-type]


# ---- 實體映射 ----


def test_to_entity_with_deferred_raw_content(session, repo):
    # raw_content / storage_path 未載入（defer）→ 以空值映射，不觸發 lazy load
    session.queue_result([_doc_model()])
    (doc,) = _run(repo.find_all_by_kb("kb-1"))

    assert doc.id.value == "doc-1"
    assert doc.kb_id == "kb-1"
    assert doc.tenant_id == "tenant-a"
    assert doc.raw_content == b""
    assert doc.storage_path == ""
    assert doc.quality_issues == ["too_short", "duplicate"]
    assert doc.source == "" and doc.source_id == ""
    assert doc.chunk_count == 3
    assert doc.quality_score == 0.8


def test_to_entity_with_loaded_raw_content(session, repo):
    session.queue_result(
        [_doc_model(raw_content=b"PDF", storage_path="t/doc-1/faq.pdf",
                    quality_issues=None, source="ingest", source_id="s-1")]
    )
    doc = _run(repo.find_by_id("doc-1"))

    assert "documents.id = 'doc-1'" in session.sql(0)
    assert doc is not None
    assert doc.raw_content == b"PDF"
    assert doc.storage_path == "t/doc-1/faq.pdf"
    assert doc.quality_issues == []
    assert (doc.source, doc.source_id) == ("ingest", "s-1")


def test_find_by_id_missing_returns_none(repo):
    assert _run(repo.find_by_id("nope")) is None


def test_chunk_to_entity_defaults(session, repo):
    session.queue_result([_chunk_model()])
    (chunk,) = _run(repo.find_chunks_by_document_paginated("doc-1", 5, 10))

    sql = session.sql(0)
    assert "chunks.document_id = 'doc-1'" in sql
    assert "LIMIT 5" in sql and "OFFSET 10" in sql
    assert chunk.id.value == "c-1"
    assert chunk.tenant_id == "tenant-a"
    assert chunk.context_text == ""
    assert chunk.metadata == {}
    assert chunk.category_id == "cat-1"
    assert chunk.quality_flag == "low"


# ---- 列表 / 計數：範圍條件 ----


def test_find_by_ids_empty_short_circuits(session, repo):
    assert _run(repo.find_by_ids([])) == []
    assert session.statements == []


def test_find_by_ids_filters_ids(session, repo):
    _run(repo.find_by_ids(["doc-1", "doc-2"]))
    assert "documents.id IN ('doc-1', 'doc-2')" in session.sql(0)


def test_find_all_by_kb_scoped_to_kb_with_paging(session, repo):
    _run(repo.find_all_by_kb("kb-1", limit=10, offset=20))
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "LIMIT 10" in sql and "OFFSET 20" in sql
    assert "documents.raw_content" not in sql.split("FROM")[0]


def test_find_top_level_by_kb_scoped_to_kb_and_top_level(session, repo):
    _run(repo.find_top_level_by_kb("kb-1", limit=10, offset=0))
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "documents.parent_id IS NULL" in sql
    assert "LIMIT 10" in sql


def test_find_stale_pending_filters_status_and_age(session, repo):
    _run(repo.find_stale_pending(T0, limit=5))
    sql = session.sql(0)
    assert "documents.status = 'pending'" in sql
    assert "documents.updated_at <" in sql
    assert "LIMIT 5" in sql


def test_find_children_scoped_to_parent(session, repo):
    session.queue_result([_doc_model(id="p1", parent_id="doc-1", page_number=1)])
    (child,) = _run(repo.find_children("doc-1"))
    assert "documents.parent_id = 'doc-1'" in session.sql(0)
    assert child.parent_id == "doc-1"
    assert child.page_number == 1


def test_count_children_by_status(session, repo):
    session.queue_result([("processed", 3), ("failed", 1)])
    counts = _run(repo.count_children_by_status("doc-1"))
    assert "documents.parent_id = 'doc-1'" in session.sql(0)
    assert counts == {"processed": 3, "failed": 1}


def test_count_by_kb(session, repo):
    session.queue_result([9])
    assert _run(repo.count_by_kb("kb-1")) == 9
    assert "documents.kb_id = 'kb-1'" in session.sql(0)


def test_count_top_level_by_kb(session, repo):
    session.queue_result([2])
    assert _run(repo.count_top_level_by_kb("kb-1")) == 2
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "documents.parent_id IS NULL" in sql


def test_count_by_kb_status(session, repo):
    session.queue_result([1])
    assert _run(repo.count_by_kb_status("kb-1", ["pending", "processing"])) == 1
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "documents.status IN ('pending', 'processing')" in sql
    assert "documents.parent_id IS NULL" in sql


def test_count_chunks_by_document(session, repo):
    session.queue_result([4])
    assert _run(repo.count_chunks_by_document("doc-1")) == 4
    assert "chunks.document_id = 'doc-1'" in session.sql(0)


def test_find_chunk_ids_by_kb_joins_documents_on_kb(session, repo):
    session.queue_result([("c1", "d1"), ("c2", "d1"), ("c3", "d2")])
    mapping = _run(repo.find_chunk_ids_by_kb("kb-1"))
    sql = session.sql(0)
    assert "JOIN documents ON chunks.document_id = documents.id" in sql
    assert "documents.kb_id = 'kb-1'" in sql
    assert mapping == {"d1": ["c1", "c2"], "d2": ["c3"]}


def test_find_chunks_by_category(session, repo):
    session.queue_result([_chunk_model()])
    (chunk,) = _run(repo.find_chunks_by_category("cat-1"))
    assert "chunks.category_id = 'cat-1'" in session.sql(0)
    assert chunk.category_id == "cat-1"


def test_find_max_updated_at_by_kb_filters_kb_and_tenant(session, repo):
    session.queue_result([T0])
    assert _run(repo.find_max_updated_at_by_kb("kb-1", "tenant-a")) == T0
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "documents.tenant_id = 'tenant-a'" in sql


def test_find_chunks_by_kb_paginated_scoped_to_kb(session, repo):
    session.queue_result([_chunk_model()])
    (chunk,) = _run(
        repo.find_chunks_by_kb_paginated("kb-1", page=3, page_size=10,
                                         category_id="cat-1")
    )
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "chunks.category_id = 'cat-1'" in sql
    assert "LIMIT 10" in sql and "OFFSET 20" in sql
    assert chunk.id.value == "c-1"


def test_find_chunks_by_kb_paginated_without_category(session, repo):
    _run(repo.find_chunks_by_kb_paginated("kb-1", page=0))
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "category_id =" not in sql
    assert "OFFSET 0" in sql


def test_count_chunks_by_kb(session, repo):
    session.queue_result([None])
    assert _run(repo.count_chunks_by_kb("kb-1", category_id="cat-1")) == 0
    sql = session.sql(0)
    assert "documents.kb_id = 'kb-1'" in sql
    assert "chunks.category_id = 'cat-1'" in sql
    _run(repo.count_chunks_by_kb("kb-1"))
    assert "category_id" not in session.sql(-1).split("WHERE")[1]


def test_find_chunk_by_id_uses_session_get(session, repo):
    assert _run(repo.find_chunk_by_id("c-1")) is None
    session.get_result = _chunk_model()
    chunk = _run(repo.find_chunk_by_id("c-1"))
    assert chunk is not None and chunk.document_id == "doc-1"


# ---- 寫入 ----


def test_save_adds_document_model(session, repo):
    doc = Document(
        id=DocumentId(value="doc-9"), kb_id="kb-1", tenant_id="tenant-a",
        filename="a.txt", content_type="text/plain", raw_content=b"",
        source="", source_id="",
    )
    _run(repo.save(doc))
    (added,) = session.added
    assert isinstance(added, DocumentModel)
    assert (added.id, added.kb_id, added.tenant_id) == ("doc-9", "kb-1", "tenant-a")
    assert added.raw_content is None  # b"" → NULL
    assert session.commits == 1


def test_delete_removes_chunks_then_document(session, repo):
    _run(repo.delete("doc-1"))
    chunks_sql, doc_sql = session.all_sql()
    assert chunks_sql.startswith("DELETE FROM chunks")
    assert "chunks.document_id = 'doc-1'" in chunks_sql
    assert doc_sql.startswith("DELETE FROM documents")
    assert "documents.id = 'doc-1'" in doc_sql


def test_update_status_with_and_without_chunk_count(session, repo):
    _run(repo.update_status("doc-1", "processed", chunk_count=5))
    sql = session.sql(-1)
    assert "UPDATE documents" in sql and "documents.id = 'doc-1'" in sql
    assert "status='processed'" in sql and "chunk_count=5" in sql
    _run(repo.update_status("doc-1", "failed"))
    assert "chunk_count" not in session.sql(-1)


def test_update_storage_path_and_content(session, repo):
    _run(repo.update_storage_path("doc-1", "t/x"))
    assert "storage_path='t/x'" in session.sql(-1)
    _run(repo.update_content("doc-1", "新內容"))
    sql = session.sql(-1)
    assert "content='新內容'" in sql and "documents.id = 'doc-1'" in sql


def test_update_quality_joins_issues(session, repo):
    _run(repo.update_quality("doc-1", 0.5, 10, 5, 20, ["a", "b"]))
    sql = session.sql(-1)
    assert "quality_issues='a,b'" in sql
    assert "documents.id = 'doc-1'" in sql


def test_save_chunks_adds_models(session, repo):
    chunk = Chunk(
        id=ChunkId(value="c-9"), document_id="doc-1", tenant_id="tenant-a",
        content="x", context_text="ctx", chunk_index=1, metadata={"p": 1},
    )
    _run(repo.save_chunks([chunk]))
    (added,) = session.added
    assert isinstance(added, ChunkModel)
    assert (added.tenant_id, added.document_id) == ("tenant-a", "doc-1")
    assert added.metadata_ == {"p": 1}


def test_delete_chunks_by_document(session, repo):
    _run(repo.delete_chunks_by_document("doc-1"))
    sql = session.sql(0)
    assert sql.startswith("DELETE FROM chunks")
    assert "chunks.document_id = 'doc-1'" in sql


def test_update_chunks_category(session, repo):
    _run(repo.update_chunks_category([], "cat-1"))
    assert session.statements == []
    _run(repo.update_chunks_category(["c1", "c2"], None))
    sql = session.sql(0)
    assert "chunks.id IN ('c1', 'c2')" in sql
    assert "category_id=NULL" in sql


def test_update_chunk_requires_a_field(repo):
    with pytest.raises(ValueError):
        _run(repo.update_chunk("c-1"))


def test_update_chunk_sets_only_given_fields(session, repo):
    _run(repo.update_chunk("c-1", content="new"))
    sql = session.sql(-1)
    assert "content='new'" in sql and "context_text" not in sql
    _run(repo.update_chunk("c-1", context_text="ctx"))
    sql = session.sql(-1)
    assert "context_text='ctx'" in sql and "chunks.id = 'c-1'" in sql


def test_delete_chunk(session, repo):
    _run(repo.delete_chunk("c-1"))
    sql = session.sql(0)
    assert sql.startswith("DELETE FROM chunks") and "chunks.id = 'c-1'" in sql
