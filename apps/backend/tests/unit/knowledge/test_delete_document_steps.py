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
    # Cascade: delete use case 會問 children；預設沒 children
    repo.find_children = AsyncMock(return_value=[])
    repo.count_by_kb = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.delete = AsyncMock()
    return store


@pytest.fixture
def mock_file_storage():
    storage = AsyncMock()
    storage.delete = AsyncMock()
    return storage


@pytest.fixture
def delete_use_case(mock_doc_repo, mock_vector_store, mock_file_storage):
    return DeleteDocumentUseCase(
        document_repository=mock_doc_repo,
        vector_store=mock_vector_store,
        document_file_storage=mock_file_storage,
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
    # Cascade fix：sed cas 子頁也會被刪，所以 delete 不一定 called_once；
    # 只驗證父 doc-001 在 call list 中
    deleted_ids = {
        call.args[0] for call in mock_doc_repo.delete.call_args_list
    }
    assert "doc-001" in deleted_ids


@then("對應的向量資料應從 Milvus 移除")
def vectors_deleted(context, mock_vector_store):
    # Cascade fix：filter 改用 list（IN operator）一次刪父 + children；
    # 沒 children 時 list 只含父 doc_id
    mock_vector_store.delete.assert_called_once_with(
        collection=f"kb_{context['kb_id']}",
        filters={"document_id": ["doc-001"]},
    )


@then("對應的文字分塊應從資料庫移除")
def chunks_deleted(context, mock_doc_repo):
    # Chunks are now deleted internally by document_repo.delete()
    deleted_ids = {
        call.args[0] for call in mock_doc_repo.delete.call_args_list
    }
    assert "doc-001" in deleted_ids


@then("應拋出 EntityNotFoundError")
def raises_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)


# ---------------------------------------------------------------------------
# Cascade delete scenario
# ---------------------------------------------------------------------------


@given(parsers.parse("文件 \"{doc_id}\" 有 {n:d} 個 child 子頁文件"))
def doc_has_children(context, mock_doc_repo, doc_id, n):
    now = datetime.now(timezone.utc)
    children = [
        Document(
            id=DocumentId(value=f"child-{i:03d}"),
            kb_id=context["kb_id"],
            tenant_id="tenant-001",
            filename=f"page_{i:03d}.png",
            content_type="image/png",
            content="",
            storage_path=f"tenant/dm/page_{i:03d}.png",
            status="processed",
            parent_id=doc_id,
            page_number=i,
            chunk_count=2,
            created_at=now,
            updated_at=now,
        )
        for i in range(1, n + 1)
    ]
    mock_doc_repo.find_children = AsyncMock(return_value=children)
    context["children"] = children
    context["expected_doc_ids"] = [doc_id] + [c.id.value for c in children]


@then("Milvus delete filter 應同時帶父與所有 children 的 document_id list")
def vectors_deleted_with_children(context, mock_vector_store):
    mock_vector_store.delete.assert_called_once()
    call_kwargs = mock_vector_store.delete.call_args.kwargs
    assert call_kwargs["collection"] == f"kb_{context['kb_id']}"
    doc_ids = call_kwargs["filters"]["document_id"]
    assert isinstance(doc_ids, list), (
        f"Expected document_id to be a list (IN operator), got {type(doc_ids)}"
    )
    assert sorted(doc_ids) == sorted(context["expected_doc_ids"])


@then("所有 children 也應從資料庫移除")
def children_deleted(context, mock_doc_repo):
    deleted_ids = {
        call.args[0] for call in mock_doc_repo.delete.call_args_list
    }
    expected = set(context["expected_doc_ids"])
    assert deleted_ids == expected, (
        f"Expected to delete {expected}, actually deleted {deleted_ids}"
    )
