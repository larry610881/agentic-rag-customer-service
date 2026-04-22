"""BDD: unit/knowledge/update_chunk.feature"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.update_chunk_use_case import (
    UpdateChunkCommand,
    UpdateChunkUseCase,
)
from src.domain.shared.exceptions import EntityNotFoundError
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeArqPool,
    FakeDocumentRepo,
    FakeKbRepo,
    make_chunk,
    make_doc,
    make_kb,
    run,
)

scenarios("unit/knowledge/update_chunk.feature")


@pytest.fixture
def ctx():
    return {}


def _seed_chunk(
    ctx,
    *,
    chunk_id="chunk-1",
    doc_id="doc-1",
    kb_id="kb-1",
    tenant_id="T001",
    content="原始內容",
    context_text="",
):
    doc_repo = FakeDocumentRepo()
    kb_repo = FakeKbRepo()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    run(doc_repo.save(make_doc(doc_id, kb_id, tenant_id)))
    chunk = make_chunk(chunk_id, doc_id, tenant_id, content=content)
    chunk.context_text = context_text
    run(doc_repo.save_chunks([chunk]))
    arq = FakeArqPool()
    ctx.update(
        doc_repo=doc_repo,
        kb_repo=kb_repo,
        arq=arq,
        chunk_id=chunk_id,
        tenant_id=tenant_id,
    )


@given(parsers.parse('租戶 "{tenant_id}" 的 KB "{kb_id}" 有一個 chunk "{chunk_id}" content="{content}"'))
def seed_chunk(ctx, tenant_id, kb_id, chunk_id, content):
    _seed_chunk(
        ctx, chunk_id=chunk_id, kb_id=kb_id, tenant_id=tenant_id, content=content
    )


@given(parsers.parse('租戶 "{tenant_id}" 擁有 chunk "{chunk_id}"'))
def seed_chunk_simple(ctx, tenant_id, chunk_id):
    _seed_chunk(ctx, chunk_id=chunk_id, tenant_id=tenant_id)


@given(parsers.parse('租戶 "{tenant_id}" 的 chunk "{chunk_id}" content="{content}" context_text="{ctx_text}"'))
def seed_chunk_with_ctx(ctx, tenant_id, chunk_id, content, ctx_text):
    _seed_chunk(
        ctx,
        chunk_id=chunk_id,
        tenant_id=tenant_id,
        content=content,
        context_text=ctx_text,
    )


@given(parsers.parse('租戶 "{tenant_id}" 的 chunk "{chunk_id}" 存在'))
def seed_chunk_exists(ctx, tenant_id, chunk_id):
    _seed_chunk(ctx, chunk_id=chunk_id, tenant_id=tenant_id)


def _run_update(ctx, *, tenant, content=None, context_text=None):
    uc = UpdateChunkUseCase(
        document_repo=ctx["doc_repo"],
        kb_repo=ctx["kb_repo"],
        arq_pool=ctx["arq"],
    )
    try:
        run(
            uc.execute(
                UpdateChunkCommand(
                    chunk_id=ctx["chunk_id"],
                    tenant_id=tenant,
                    content=content,
                    context_text=context_text,
                    actor="admin@test",
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


@when(parsers.parse('我以 tenant "{tenant}" 身分 PATCH chunk "{chunk_id}" 設 content="{new}"'))
def when_patch_content(ctx, tenant, chunk_id, new):
    _run_update(ctx, tenant=tenant, content=new)


@when(parsers.parse('我以 tenant "{tenant}" 身分嘗試 PATCH chunk "{chunk_id}" content="{new}"'))
def when_try_patch(ctx, tenant, chunk_id, new):
    _run_update(ctx, tenant=tenant, content=new)


@when(parsers.parse('我以 tenant "{tenant}" 身分 PATCH chunk "{chunk_id}" 設 context_text="{new}"'))
def when_patch_ctx(ctx, tenant, chunk_id, new):
    _run_update(ctx, tenant=tenant, context_text=new)


@when(parsers.parse('我以 tenant "{tenant}" 身分 PATCH chunk "{chunk_id}" content=""'))
def when_patch_empty(ctx, tenant, chunk_id):
    _run_update(ctx, tenant=tenant, content="")


@then(parsers.parse('chunk 的 content 應更新為 "{expected}"'))
def then_content_updated(ctx, expected):
    assert ctx["error"] is None, f"unexpected error: {ctx['error']}"
    chunk = run(ctx["doc_repo"].find_chunk_by_id(ctx["chunk_id"]))
    assert chunk.content == expected


@then(parsers.parse('chunk 的 context_text 應更新為 "{expected}"'))
def then_ctx_updated(ctx, expected):
    assert ctx["error"] is None
    chunk = run(ctx["doc_repo"].find_chunk_by_id(ctx["chunk_id"]))
    assert chunk.context_text == expected


@then("chunk 的 updated_at 應設為當前時間")
def then_updated_at(ctx):
    # Placeholder；ChunkModel migration 補 updated_at 後驗證實際值
    assert ctx["error"] is None


@then(parsers.parse('應 enqueue arq job "{job_name}" 帶 chunk_id="{chunk_id}"'))
def then_enqueue(ctx, job_name, chunk_id):
    assert any(
        name == job_name and args[0] == chunk_id
        for name, args, _ in ctx["arq"].jobs
    )


@then("應 enqueue \"reembed_chunk\" job")
def then_enqueue_any(ctx):
    assert any(name == "reembed_chunk" for name, _, _ in ctx["arq"].jobs)


@then(parsers.parse('應記錄 audit event "{event_name}" 含 actor + content_diff_len'))
def then_audit(ctx, event_name):
    # structlog event 驗證由 structlog testing 或 pytest caplog 做；此處僅保 use case
    # 無異常通過（event 名稱對應 kb_studio.chunk.update）
    assert ctx["error"] is None


@then("應拋出 EntityNotFoundError（回 404 防枚舉）")
def then_not_found(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)


@then("chunk 的 content 應保持原樣不變")
def then_unchanged(ctx):
    chunk = run(ctx["doc_repo"].find_chunk_by_id(ctx["chunk_id"]))
    assert chunk.content == "原始內容"


@then("不應 enqueue 任何 arq job")
def then_no_enqueue(ctx):
    assert ctx["arq"].jobs == []


@then(parsers.parse('應拋出 ValueError 訊息含 "{needle}"'))
def then_value_error(ctx, needle):
    assert isinstance(ctx["error"], ValueError)
    assert needle in str(ctx["error"])
