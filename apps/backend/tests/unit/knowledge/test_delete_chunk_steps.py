"""BDD: unit/knowledge/delete_chunk.feature — Phase D Outbox 化"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.delete_chunk_use_case import (
    DeleteChunkCommand,
    DeleteChunkUseCase,
)
from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.outbox.entity import OutboxEvent, OutboxEventType
from src.domain.outbox.repository import OutboxEventRepository
from src.domain.shared.exceptions import EntityNotFoundError
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeDocumentRepo,
    FakeKbRepo,
    FakeVectorStore,
    make_chunk,
    make_doc,
    make_kb,
    run,
)

scenarios("unit/knowledge/delete_chunk.feature")


# ── Recording outbox repo (in-memory) ──────────────────────────────


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


@pytest.fixture
def ctx():
    return {}


def _seed(ctx, *, tenant_id="T001", kb_id="kb-1", doc_id="doc-1", chunk_id="chunk-1"):
    doc_repo = FakeDocumentRepo()
    kb_repo = FakeKbRepo()
    vs = FakeVectorStore()
    outbox_repo = _RecordingOutboxRepo()
    publish_outbox = PublishOutboxEventUseCase(outbox_repo=outbox_repo)
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    run(doc_repo.save(make_doc(doc_id, kb_id, tenant_id)))
    run(doc_repo.save_chunks([make_chunk(chunk_id, doc_id, tenant_id)]))
    ctx.update(
        doc_repo=doc_repo,
        kb_repo=kb_repo,
        vs=vs,
        outbox_repo=outbox_repo,
        publish_outbox=publish_outbox,
        chunk_id=chunk_id,
        kb_id=kb_id,
    )


@given(parsers.parse(
    '租戶 "{tenant_id}" 的 chunk "{chunk_id}" 存在於 DB 與 Milvus collection '
    '"{collection}"'
))
def seed_with_milvus(ctx, tenant_id, chunk_id, collection):
    _seed(
        ctx, tenant_id=tenant_id, chunk_id=chunk_id,
        kb_id=collection.replace("kb_", ""),
    )


@given(parsers.parse('租戶 "{tenant_id}" 擁有 chunk "{chunk_id}"'))
def seed_owner(ctx, tenant_id, chunk_id):
    _seed(ctx, tenant_id=tenant_id, chunk_id=chunk_id)


def _run_delete(ctx, tenant):
    uc = DeleteChunkUseCase(
        document_repo=ctx["doc_repo"],
        kb_repo=ctx["kb_repo"],
        publish_outbox_event_use_case=ctx["publish_outbox"],
    )
    try:
        run(uc.execute(DeleteChunkCommand(chunk_id=ctx["chunk_id"], tenant_id=tenant)))
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


@when(parsers.parse('我以 tenant "{tenant}" 身分 DELETE chunk "{chunk_id}"'))
def when_delete(ctx, tenant, chunk_id):
    _run_delete(ctx, tenant)


@when(parsers.parse('我以 tenant "{tenant}" 身分嘗試 DELETE chunk "{chunk_id}"'))
def when_try_delete(ctx, tenant, chunk_id):
    _run_delete(ctx, tenant)


@then("chunk 應從 DB 刪除")
def then_db_deleted(ctx):
    assert run(ctx["doc_repo"].find_chunk_by_id(ctx["chunk_id"])) is None


@then(parsers.parse("應發布 {count:d} 筆 vector.delete outbox 事件"))
def assert_outbox_count(ctx, count: int):
    delete_events = [
        e for e in ctx["outbox_repo"].events
        if e.event_type == OutboxEventType.VECTOR_DELETE.value
    ]
    assert len(delete_events) == count


@then(parsers.parse('該事件的 collection 應為 "{expected}"'))
def assert_collection(ctx, expected: str):
    e = ctx["outbox_repo"].events[0]
    assert e.payload.get("collection") == expected


@then(parsers.parse('該事件的 filters.id 應為 "{expected}"'))
def assert_filters_id(ctx, expected: str):
    e = ctx["outbox_repo"].events[0]
    assert e.payload.get("filters", {}).get("id") == expected


@then("該事件不應帶 doc_watermark_ts")
def assert_no_watermark(ctx):
    e = ctx["outbox_repo"].events[0]
    assert e.doc_watermark_ts is None


@then("不應直接呼叫 vector store")
def assert_no_vs_call(ctx):
    assert ctx["vs"].deletes == []


@then("應拋出 EntityNotFoundError")
def then_entity_not_found(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)


@then("不應發布任何 outbox 事件")
def assert_no_outbox(ctx):
    assert ctx["outbox_repo"].events == []


@then("chunk 應保持存在於 DB")
def then_chunk_still_exists(ctx):
    assert run(ctx["doc_repo"].find_chunk_by_id(ctx["chunk_id"])) is not None
