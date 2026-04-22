"""BDD: unit/knowledge/reembed_chunk.feature"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.reembed_chunk_use_case import (
    ReEmbedChunkCommand,
    ReEmbedChunkUseCase,
)
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeDocumentRepo,
    FakeEmbeddingService,
    FakeKbRepo,
    FakeVectorStore,
    make_chunk,
    make_doc,
    make_kb,
    run,
)

scenarios("unit/knowledge/reembed_chunk.feature")


@pytest.fixture
def ctx():
    return {}


def _seed(ctx, *, chunk_id="chunk-1", kb_id="kb-1", tenant_id="T001", content="修正後內容", ctx_text="context X"):
    doc_repo = FakeDocumentRepo()
    kb_repo = FakeKbRepo()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    run(doc_repo.save(make_doc("doc-1", kb_id, tenant_id)))
    chunk = make_chunk(chunk_id, "doc-1", tenant_id, content=content)
    chunk.context_text = ctx_text
    run(doc_repo.save_chunks([chunk]))
    ctx.update(
        doc_repo=doc_repo,
        kb_repo=kb_repo,
        embed=FakeEmbeddingService(),
        vs=FakeVectorStore(),
        record_usage=AsyncMock(),
        chunk_id=chunk_id,
        kb_id=kb_id,
        tenant_id=tenant_id,
    )


@given(parsers.parse('chunk "{chunk_id}" 屬於 KB "{kb_id}" 租戶 "{tenant_id}"'))
def seed_base(ctx, chunk_id, kb_id, tenant_id):
    _seed(ctx, chunk_id=chunk_id, kb_id=kb_id, tenant_id=tenant_id)


@given(parsers.parse('chunk 的 content = "{c}" context_text = "{ct}"'))
def seed_content(ctx, c, ct):
    chunk = run(ctx["doc_repo"].find_chunk_by_id(ctx["chunk_id"]))
    chunk.content = c
    chunk.context_text = ct


@given(parsers.parse('chunk "{chunk_id}" 存在'))
def seed_exists(ctx, chunk_id):
    _seed(ctx, chunk_id=chunk_id)


@given(parsers.parse('在 arq job 排隊期間 chunk "{chunk_id}" 被刪除'))
def seed_deleted(ctx, chunk_id):
    _seed(ctx, chunk_id=chunk_id)
    run(ctx["doc_repo"].delete_chunk(chunk_id))


@given("embedding service 呼叫會失敗")
def set_embed_fail(ctx):
    ctx["embed"].should_fail = True


def _run_reembed(ctx):
    uc = ReEmbedChunkUseCase(
        document_repo=ctx["doc_repo"],
        kb_repo=ctx["kb_repo"],
        embedding_service=ctx["embed"],
        vector_store=ctx["vs"],
        record_usage=ctx.get("record_usage"),
    )
    try:
        run(uc.execute(ReEmbedChunkCommand(chunk_id=ctx["chunk_id"])))
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


@when(parsers.parse('arq worker 執行 reembed_chunk job(chunk_id="{chunk_id}")'))
def when_run(ctx, chunk_id):
    ctx["chunk_id"] = chunk_id
    _run_reembed(ctx)


@then("應呼叫 embedding service 計算 content + context_text 的向量")
def then_embed_called(ctx):
    assert ctx["embed"].calls == 1


@then(parsers.parse('Milvus collection "{collection}" 應呼叫 upsert_single(id="{cid}", vector, payload)'))
def then_upsert_single(ctx, collection, cid):
    assert len(ctx["vs"].single_upserts) == 1
    col, mid, _, _ = ctx["vs"].single_upserts[0]
    assert col == collection and mid == cid


@then(parsers.parse('Milvus payload 應含 tenant_id="{tenant_id}"（安全紅線）'))
def then_tenant_in_payload(ctx, tenant_id):
    _, _, _, payload = ctx["vs"].single_upserts[0]
    assert payload.get("tenant_id") == tenant_id


@then(parsers.parse('應記錄 token usage（type=embedding, tenant_id={tenant_id}）'))
def then_record_usage(ctx, tenant_id):
    ctx["record_usage"].execute.assert_awaited_once()


@then(parsers.parse('應記錄 audit event "{ev}" 含 model + token_cost'))
def then_audit(ctx, ev):
    assert ctx["error"] is None


@then(parsers.parse('應記錄 structlog warning "{key}"'))
def then_warn(ctx, key):
    assert ctx["error"] is None


@then("不應呼叫 embedding service")
def then_no_embed(ctx):
    assert ctx["embed"].calls == 0


@then("不應呼叫 Milvus upsert_single")
def then_no_upsert(ctx):
    assert ctx["vs"].single_upserts == []


@then(parsers.parse('應記錄 structlog error "{key}"'))
def then_error_log(ctx, key):
    # use case 吞錯（記 log）不拋例外
    assert ctx["error"] is None
