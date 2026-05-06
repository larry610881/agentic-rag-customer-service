"""刪除知識庫文件 BDD Step Definitions（Phase C — Outbox Pattern）"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.delete_document_use_case import (
    DeleteDocumentUseCase,
)
from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.knowledge.entity import Document
from src.domain.knowledge.value_objects import DocumentId
from src.domain.outbox.entity import OutboxEvent, OutboxEventType
from src.domain.outbox.repository import OutboxEventRepository
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/knowledge/delete_document.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── In-memory fake outbox repo ────────────────────────────────────


class _RecordingOutboxRepo(OutboxEventRepository):
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    async def save(self, event: OutboxEvent) -> None:
        self.events.append(event)

    async def claim_batch(self, *args, **kwargs):  # noqa: ANN001
        return []

    async def update(self, event: OutboxEvent) -> None:
        return None

    async def find_by_id(self, event_id: str) -> OutboxEvent | None:
        return None

    async def list_dead_letter(self, **kwargs) -> list[OutboxEvent]:
        return []

    async def count_by_status(self, status: str) -> int:
        return 0

    async def oldest_pending_age_seconds(self) -> float | None:
        return None

    async def delete(self, event_id: str) -> None:
        return None


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_doc_repo():
    repo = AsyncMock()
    repo.delete = AsyncMock()
    repo.find_children = AsyncMock(return_value=[])
    repo.count_by_kb = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def outbox_repo():
    return _RecordingOutboxRepo()


@pytest.fixture
def publish_outbox(outbox_repo):
    return PublishOutboxEventUseCase(outbox_repo=outbox_repo)


@pytest.fixture
def mock_vector_store():
    """殘留 mock — 用於確認 use case **不會** 直接呼叫 vector store."""
    return AsyncMock()


@pytest.fixture
def mock_file_storage():
    storage = AsyncMock()
    storage.delete = AsyncMock()
    return storage


@pytest.fixture
def delete_use_case(mock_doc_repo, publish_outbox, mock_file_storage):
    return DeleteDocumentUseCase(
        document_repository=mock_doc_repo,
        publish_outbox_event_use_case=publish_outbox,
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
    deleted_ids = {
        call.args[0] for call in mock_doc_repo.delete.call_args_list
    }
    assert "doc-001" in deleted_ids


@then(parsers.parse("應發布 {count:d} 筆 vector.delete outbox 事件"))
def assert_outbox_event_count(outbox_repo, count: int):
    delete_events = [
        e for e in outbox_repo.events
        if e.event_type == OutboxEventType.VECTOR_DELETE.value
    ]
    assert len(delete_events) == count


@then(parsers.parse('該事件的 collection 應為 "{expected}"'))
def assert_event_collection(outbox_repo, expected: str):
    delete_events = [
        e for e in outbox_repo.events
        if e.event_type == OutboxEventType.VECTOR_DELETE.value
    ]
    assert delete_events
    assert delete_events[0].payload.get("collection") == expected


@then(parsers.parse('該事件的 filters.document_id 應只含 "{doc_id}"'))
def assert_filter_single_doc(outbox_repo, doc_id: str):
    delete_events = [
        e for e in outbox_repo.events
        if e.event_type == OutboxEventType.VECTOR_DELETE.value
    ]
    assert delete_events
    filters = delete_events[0].payload.get("filters", {})
    doc_ids = filters.get("document_id")
    assert isinstance(doc_ids, list)
    assert doc_ids == [doc_id]


@then("該事件應帶 doc_watermark_ts 等於 parent doc.created_at")
def assert_watermark(context, outbox_repo):
    delete_events = [
        e for e in outbox_repo.events
        if e.event_type == OutboxEventType.VECTOR_DELETE.value
    ]
    assert delete_events
    assert delete_events[0].doc_watermark_ts == context["doc"].created_at


@then("不應直接呼叫 vector store")
def assert_no_vector_store_call(mock_vector_store):
    mock_vector_store.delete.assert_not_called()
    mock_vector_store.drop_collection.assert_not_called()


@then("應拋出 EntityNotFoundError")
def raises_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)


@then("不應發布任何 outbox 事件")
def assert_no_outbox(outbox_repo):
    assert outbox_repo.events == []


# ── Cascade scenarios ────────────────────────────────────────────


@given(parsers.parse('文件 "{doc_id}" 有 {n:d} 個 child 子頁文件'))
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


@then(
    "該事件的 filters.document_id 應同時帶父與所有 children 的 document_id"
)
def assert_filter_with_children(context, outbox_repo):
    delete_events = [
        e for e in outbox_repo.events
        if e.event_type == OutboxEventType.VECTOR_DELETE.value
    ]
    assert delete_events
    filters = delete_events[0].payload.get("filters", {})
    doc_ids = filters.get("document_id")
    assert isinstance(doc_ids, list)
    assert sorted(doc_ids) == sorted(context["expected_doc_ids"])


@then("所有 children 也應從資料庫移除")
def children_deleted(context, mock_doc_repo):
    deleted_ids = {
        call.args[0] for call in mock_doc_repo.delete.call_args_list
    }
    expected = set(context["expected_doc_ids"])
    assert deleted_ids == expected
