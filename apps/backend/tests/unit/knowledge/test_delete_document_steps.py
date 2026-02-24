"""刪除知識庫文件 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.delete_document_use_case import DeleteDocumentUseCase
from src.domain.knowledge.entity import Document
from src.domain.knowledge.value_objects import DocumentId
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/knowledge/delete_document.feature")


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
def mock_doc_repo():
    repo = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_chunk_repo():
    repo = AsyncMock()
    repo.delete_by_document = AsyncMock()
    return repo


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.delete = AsyncMock()
    return store


@pytest.fixture
def delete_use_case(mock_doc_repo, mock_chunk_repo, mock_vector_store):
    return DeleteDocumentUseCase(
        document_repository=mock_doc_repo,
        chunk_repository=mock_chunk_repo,
        vector_store=mock_vector_store,
    )


@given(parsers.parse('知識庫 "{kb_id}" 存在'))
def kb_exists(context, kb_id):
    context["kb_id"] = kb_id


@given(parsers.parse('文件 "{doc_id}" 已上傳且狀態為 "{doc_status}"'))
def doc_uploaded(context, mock_doc_repo, doc_id, doc_status):
    now = datetime.now(timezone.utc)
    doc = Document(
        id=DocumentId(value=doc_id),
        kb_id=context["kb_id"],
        tenant_id="tenant-001",
        filename="test.txt",
        content_type="text/plain",
        content="content",
        status=doc_status,
        chunk_count=5,
        created_at=now,
        updated_at=now,
    )
    mock_doc_repo.find_by_id = AsyncMock(return_value=doc)
    context["doc"] = doc


@when(parsers.parse('刪除文件 "{doc_id}"'))
def delete_document(context, delete_use_case, mock_doc_repo, doc_id):
    if doc_id == "nonexistent":
        mock_doc_repo.find_by_id = AsyncMock(return_value=None)
    try:
        _run(delete_use_case.execute(doc_id))
        context["error"] = None
    except EntityNotFoundError as e:
        context["error"] = e


@then("文件應從資料庫移除")
def doc_deleted(context, mock_doc_repo):
    mock_doc_repo.delete.assert_called_once_with("doc-001")


@then("對應的向量資料應從 Qdrant 移除")
def vectors_deleted(context, mock_vector_store):
    mock_vector_store.delete.assert_called_once_with(
        collection=f"kb_{context['kb_id']}",
        filters={"document_id": "doc-001"},
    )


@then("對應的文字分塊應從資料庫移除")
def chunks_deleted(context, mock_chunk_repo):
    mock_chunk_repo.delete_by_document.assert_called_once_with("doc-001")


@then("應拋出 EntityNotFoundError")
def raises_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)
