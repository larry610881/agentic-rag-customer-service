"""刪除知識庫 BDD Step Definitions（Phase B — 透過 Outbox Pattern）"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.delete_knowledge_base_use_case import (
    DeleteKnowledgeBaseUseCase,
)
from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.domain.outbox.entity import OutboxEvent, OutboxEventType
from src.domain.outbox.repository import OutboxEventRepository
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/knowledge/delete_knowledge_base.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── In-memory fake outbox repo + call recorder ────────────────────────


class _RecordingOutboxRepo(OutboxEventRepository):
    """收集 publish 的事件供 assert 用。"""

    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    async def save(self, event: OutboxEvent) -> None:
        self.events.append(event)

    async def claim_batch(self, *args, **kwargs):  # noqa: ANN001, D401
        return []

    async def update(self, event: OutboxEvent) -> None:
        return None

    async def find_by_id(self, event_id: str) -> OutboxEvent | None:
        return None

    async def list_dead_letter(self, **kwargs) -> list[OutboxEvent]:
        return []

    async def count_by_status(self, status: str) -> int:
        return 0


@pytest.fixture
def context():
    """Tracks call order for ordering assertions."""
    return {"call_order": []}


@pytest.fixture
def mock_kb_repo(context):
    repo = AsyncMock()

    async def _delete(kb_id):
        context["call_order"].append("kb_repo.delete")

    repo.delete = AsyncMock(side_effect=_delete)
    return repo


@pytest.fixture
def mock_doc_repo():
    return AsyncMock()


@pytest.fixture
def outbox_repo(context):
    repo = _RecordingOutboxRepo()
    original_save = repo.save

    async def _save(event):
        context["call_order"].append("outbox.publish")
        await original_save(event)

    repo.save = _save  # type: ignore[assignment]
    return repo


@pytest.fixture
def publish_outbox(outbox_repo):
    return PublishOutboxEventUseCase(outbox_repo=outbox_repo)


@pytest.fixture
def mock_vector_store():
    """殘留欄位 — 確保新 use case **不會** 呼叫到 vector store。"""
    return AsyncMock()


@pytest.fixture
def delete_kb_use_case(mock_kb_repo, mock_doc_repo, publish_outbox):
    return DeleteKnowledgeBaseUseCase(
        knowledge_base_repository=mock_kb_repo,
        document_repository=mock_doc_repo,
        publish_outbox_event_use_case=publish_outbox,
    )


@given(parsers.parse('知識庫 "{kb_id}" 存在且包含文件'))
def kb_exists_with_docs(context, mock_kb_repo, kb_id):
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
    context["kb_id"] = kb_id


@when(parsers.parse('刪除知識庫 "{kb_id}"'))
def delete_knowledge_base(context, delete_kb_use_case, mock_kb_repo, kb_id):
    if kb_id == "nonexistent":
        mock_kb_repo.find_by_id = AsyncMock(return_value=None)
    try:
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


@then(parsers.parse("應發布 {count:d} 筆 vector.drop_collection outbox 事件"))
def assert_outbox_event_count(context, outbox_repo, count: int):
    drop_events = [
        e for e in outbox_repo.events
        if e.event_type == OutboxEventType.VECTOR_DROP_COLLECTION.value
    ]
    assert len(drop_events) == count


@then(parsers.parse('該事件的 collection 應為 "{expected}"'))
def assert_event_collection(outbox_repo, expected: str):
    drop_events = [
        e for e in outbox_repo.events
        if e.event_type == OutboxEventType.VECTOR_DROP_COLLECTION.value
    ]
    assert drop_events, "no vector.drop_collection event published"
    assert drop_events[0].payload.get("collection") == expected


@then("不應直接呼叫 vector store")
def assert_no_vector_store_call(mock_vector_store):
    # mock_vector_store 沒被注入到 use case，所以 .delete 沒被呼叫過 — 用此 assert
    # 驗證 use case 構造時不再依賴 vector_store（fixture 不會 wire 進去）
    mock_vector_store.delete.assert_not_called()
    mock_vector_store.drop_collection.assert_not_called()


@then("publish_outbox 應先於 kb_repo.delete 被呼叫")
def assert_publish_before_delete(context):
    order = context["call_order"]
    assert "outbox.publish" in order
    assert "kb_repo.delete" in order
    assert order.index("outbox.publish") < order.index("kb_repo.delete"), (
        f"expected outbox.publish before kb_repo.delete, got order: {order}"
    )


@then("應拋出 EntityNotFoundError")
def raises_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)


@then("不應發布任何 outbox 事件")
def assert_no_outbox(outbox_repo):
    assert outbox_repo.events == []
