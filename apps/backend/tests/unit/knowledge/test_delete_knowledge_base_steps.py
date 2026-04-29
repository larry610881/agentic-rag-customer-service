"""刪除知識庫 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.delete_knowledge_base_use_case import (
    DeleteKnowledgeBaseUseCase,
)
from src.domain.knowledge.entity import Document, KnowledgeBase
from src.domain.knowledge.value_objects import DocumentId, KnowledgeBaseId
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/knowledge/delete_knowledge_base.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_kb_repo():
    repo = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_doc_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.delete = AsyncMock()
    return store


@pytest.fixture
def delete_kb_use_case(mock_kb_repo, mock_doc_repo, mock_vector_store):
    return DeleteKnowledgeBaseUseCase(
        knowledge_base_repository=mock_kb_repo,
        document_repository=mock_doc_repo,
        vector_store=mock_vector_store,
    )


@given(parsers.parse('知識庫 "{kb_id}" 存在且包含文件'))
def kb_exists_with_docs(context, mock_kb_repo, mock_doc_repo, kb_id):
    now = datetime.now(timezone.utc)
    kb = KnowledgeBase(
        id=KnowledgeBaseId(value=kb_id),
        tenant_id="tenant-001",
        name="測試知識庫",
        description="測試用",
        kb_type="user",
        created_at=now,
        updated_at=now,
    )
    mock_kb_repo.find_by_id = AsyncMock(return_value=kb)

    docs = [
        Document(
            id=DocumentId(value="doc-001"),
            kb_id=kb_id,
            tenant_id="tenant-001",
            filename="file1.txt",
            content_type="text/plain",
            content="content1",
            status="processed",
            chunk_count=3,
            created_at=now,
            updated_at=now,
        ),
        Document(
            id=DocumentId(value="doc-002"),
            kb_id=kb_id,
            tenant_id="tenant-001",
            filename="file2.txt",
            content_type="text/plain",
            content="content2",
            status="processed",
            chunk_count=5,
            created_at=now,
            updated_at=now,
        ),
    ]
    mock_doc_repo.find_all_by_kb = AsyncMock(return_value=docs)
    context["kb_id"] = kb_id
    context["docs"] = docs


@when(parsers.parse('刪除知識庫 "{kb_id}"'))
def delete_knowledge_base(context, delete_kb_use_case, mock_kb_repo, kb_id):
    if kb_id == "nonexistent":
        mock_kb_repo.find_by_id = AsyncMock(return_value=None)
    try:
        # 新契約（2026-04-29）：execute 需 requester_tenant_id（防跨租戶刪除）
        _run(
            delete_kb_use_case.execute(
                kb_id, requester_tenant_id="tenant-001"
            )
        )
        context["error"] = None
    except EntityNotFoundError as e:
        context["error"] = e


@then("知識庫應從資料庫移除")
def kb_deleted(context, mock_kb_repo):
    mock_kb_repo.delete.assert_called_once_with(context["kb_id"])


@then("所有文件的向量資料應從 Milvus 移除")
def vectors_deleted(context, mock_vector_store):
    kb_id = context["kb_id"]
    assert mock_vector_store.delete.call_count == 2
    calls = mock_vector_store.delete.call_args_list
    call_kwargs = [c.kwargs for c in calls]
    assert {"collection": f"kb_{kb_id}", "filters": {"document_id": "doc-001"}} in call_kwargs
    assert {"collection": f"kb_{kb_id}", "filters": {"document_id": "doc-002"}} in call_kwargs


@then("所有文件及分塊應從資料庫移除")
def docs_and_chunks_deleted(context, mock_kb_repo):
    # KB repo.delete handles cascade (chunks → documents → kb)
    mock_kb_repo.delete.assert_called_once_with(context["kb_id"])


@then("應拋出 EntityNotFoundError")
def raises_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)
