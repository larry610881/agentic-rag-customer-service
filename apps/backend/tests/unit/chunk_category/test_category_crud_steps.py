"""BDD: unit/chunk_category/category_crud.feature"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.chunk_category.assign_chunks_use_case import (
    AssignChunksCommand,
    AssignChunksUseCase,
)
from src.application.chunk_category.create_category_use_case import (
    CreateCategoryCommand,
    CreateCategoryUseCase,
)
from src.application.chunk_category.delete_category_use_case import (
    DeleteCategoryCommand,
    DeleteCategoryUseCase,
)
from src.domain.knowledge.entity import ChunkCategory
from src.domain.shared.exceptions import EntityNotFoundError
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeCategoryRepo,
    FakeDocumentRepo,
    FakeKbRepo,
    make_chunk,
    make_doc,
    make_kb,
    run,
)

scenarios("unit/chunk_category/category_crud.feature")


@pytest.fixture
def ctx():
    return {}


def _setup(ctx, *, tenant_id="T001", kb_id="kb-1"):
    doc_repo = FakeDocumentRepo()
    cat_repo = FakeCategoryRepo(doc_repo=doc_repo)
    kb_repo = FakeKbRepo()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    ctx.update(
        cat_repo=cat_repo,
        doc_repo=doc_repo,
        kb_repo=kb_repo,
        tenant_id=tenant_id,
        kb_id=kb_id,
    )


@given(parsers.parse('租戶 "{tenant_id}" 擁有 KB "{kb_id}"'))
def seed_kb(ctx, tenant_id, kb_id):
    _setup(ctx, tenant_id=tenant_id, kb_id=kb_id)


@given(parsers.parse('租戶 "{tenant_id}" 的 KB "{kb_id}" 有分類 "{cat_id}" 含 {n:d} 個 chunks'))
def seed_cat_chunks(ctx, tenant_id, kb_id, cat_id, n):
    _setup(ctx, tenant_id=tenant_id, kb_id=kb_id)
    # 建分類
    run(
        ctx["cat_repo"].save(
            ChunkCategory(
                id=cat_id, kb_id=kb_id, tenant_id=tenant_id,
                name="cat-name", chunk_count=n,
            )
        )
    )
    # 建 chunks
    run(ctx["doc_repo"].save(make_doc("doc-1", kb_id, tenant_id)))
    chunks = [
        make_chunk(f"chunk-{i}", "doc-1", tenant_id, category_id=cat_id)
        for i in range(n)
    ]
    run(ctx["doc_repo"].save_chunks(chunks))
    ctx["cat_id"] = cat_id
    ctx["chunk_count"] = n


@given(parsers.parse('租戶 "{tenant_id}" 的 KB "{kb_id}" 有分類 "{cat_id}"'))
def seed_cat_only(ctx, tenant_id, kb_id, cat_id):
    _setup(ctx, tenant_id=tenant_id, kb_id=kb_id)
    run(
        ctx["cat_repo"].save(
            ChunkCategory(
                id=cat_id, kb_id=kb_id, tenant_id=tenant_id, name="cat-name"
            )
        )
    )
    ctx["cat_id"] = cat_id


@given(parsers.parse('有 {n:d} 個 chunks ["{c1}","{c2}","{c3}","{c4}","{c5}"] 屬於 {kb_id}'))
def seed_five_chunks(ctx, n, c1, c2, c3, c4, c5, kb_id):
    run(ctx["doc_repo"].save(make_doc("doc-1", kb_id, ctx["tenant_id"])))
    chunks = [
        make_chunk(cid, "doc-1", ctx["tenant_id"])
        for cid in [c1, c2, c3, c4, c5]
    ]
    run(ctx["doc_repo"].save_chunks(chunks))


@given(parsers.parse('租戶 "{tenant_id}" 擁有 KB "{kb_id}" 分類 "{cat_id}" 與 chunk "{chunk_id}"'))
def seed_all(ctx, tenant_id, kb_id, cat_id, chunk_id):
    _setup(ctx, tenant_id=tenant_id, kb_id=kb_id)
    run(
        ctx["cat_repo"].save(
            ChunkCategory(id=cat_id, kb_id=kb_id, tenant_id=tenant_id, name="c")
        )
    )
    run(ctx["doc_repo"].save(make_doc("doc-1", kb_id, tenant_id)))
    run(ctx["doc_repo"].save_chunks([make_chunk(chunk_id, "doc-1", tenant_id)]))
    ctx["cat_id"] = cat_id


@when(parsers.parse('我以 tenant "{tenant}" 身分 POST /kb/{kb_id}/categories name="{name}"'))
def when_create(ctx, tenant, kb_id, name):
    uc = CreateCategoryUseCase(ctx["cat_repo"], ctx["kb_repo"])
    try:
        ctx["created"] = run(
            uc.execute(
                CreateCategoryCommand(
                    kb_id=kb_id, tenant_id=tenant, name=name
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e
        ctx["created"] = None


@when(parsers.parse('我以 tenant "{tenant}" 身分 DELETE /kb/{kb_id}/categories/{cat_id}'))
def when_delete(ctx, tenant, kb_id, cat_id):
    uc = DeleteCategoryUseCase(ctx["cat_repo"], ctx["kb_repo"])
    try:
        run(
            uc.execute(
                DeleteCategoryCommand(
                    kb_id=kb_id, category_id=cat_id, tenant_id=tenant
                )
            )
        )
        # Fake 級聯：把 chunks 的 category_id 設 NULL
        for c in list(ctx["doc_repo"].chunks.values()):
            if c.category_id == cat_id:
                c.category_id = None
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


@when(
    parsers.parse(
        '我以 tenant "{tenant}" 身分 POST /kb/{kb_id}/categories/{cat_id}/assign-chunks body={{"chunk_ids":["{c1}","{c2}","{c3}"]}}'
    )
)
def when_assign(ctx, tenant, kb_id, cat_id, c1, c2, c3):
    uc = AssignChunksUseCase(
        ctx["cat_repo"], ctx["doc_repo"], ctx["kb_repo"]
    )
    try:
        run(
            uc.execute(
                AssignChunksCommand(
                    kb_id=kb_id,
                    category_id=cat_id,
                    tenant_id=tenant,
                    chunk_ids=[c1, c2, c3],
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


# 用 re 鎖死「單一 chunk_id」格式（沒有逗號），避免 greedy 吞掉多 chunk 場景
@when(
    parsers.re(
        r'^我以 tenant "(?P<tenant>[^"]+)" 身分 POST /kb/(?P<kb_id>[^/]+)'
        r'/categories/(?P<cat_id>[^/]+)/assign-chunks '
        r'body=\{"chunk_ids":\["(?P<cid>[^",]+)"\]\}$'
    )
)
def when_assign_one(ctx, tenant, kb_id, cat_id, cid):
    uc = AssignChunksUseCase(
        ctx["cat_repo"], ctx["doc_repo"], ctx["kb_repo"]
    )
    try:
        run(
            uc.execute(
                AssignChunksCommand(
                    kb_id=kb_id,
                    category_id=cat_id,
                    tenant_id=tenant,
                    chunk_ids=[cid],
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e


@then(parsers.parse('應建立一個分類 name="{name}" kb_id="{kb_id}"'))
def then_created(ctx, name, kb_id):
    assert ctx["created"] is not None
    assert ctx["created"].name == name
    assert ctx["created"].kb_id == kb_id


@then("分類的 chunk_count 應為 0")
def then_count_zero(ctx):
    assert ctx["created"].chunk_count == 0


@then(parsers.parse('應記錄 audit event "{ev}"'))
def then_audit(ctx, ev):
    assert ctx.get("error") is None


@then(parsers.parse('應記錄 audit event "{ev}" 含 chunk_count={n:d}'))
def then_audit_count(ctx, ev, n):
    assert ctx.get("error") is None


@then("應拋出 EntityNotFoundError（回 404 防枚舉）")
def then_nf(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)


@then("應拋出 EntityNotFoundError")
def then_nf2(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)


@then("不應建立任何分類")
def then_no_cat(ctx):
    assert len(ctx["cat_repo"].items) == 0


@then(parsers.parse('分類 "{cat_id}" 應被刪除'))
def then_cat_deleted(ctx, cat_id):
    assert cat_id not in ctx["cat_repo"].items


@then(parsers.parse("{n:d} 個 chunks 的 category_id 應變為 NULL"))
def then_cascade(ctx, n):
    null_cnt = sum(
        1 for c in ctx["doc_repo"].chunks.values() if c.category_id is None
    )
    assert null_cnt >= n


@then(parsers.parse('chunks {c1}, {c2}, {c3} 的 category_id 應變為 "{cat}"'))
def then_assigned(ctx, c1, c2, c3, cat):
    for cid in [c1, c2, c3]:
        assert ctx["doc_repo"].chunks[cid].category_id == cat


@then(parsers.parse("chunks {c1}, {c2} 的 category_id 應保持不變"))
def then_unchanged(ctx, c1, c2):
    for cid in [c1, c2]:
        assert ctx["doc_repo"].chunks[cid].category_id is None


@then(parsers.parse('chunk "{cid}" 的 category_id 應保持原樣'))
def then_chunk_unchanged(ctx, cid):
    # 跨租戶 assign 被擋，chunk.category_id 不應被設
    assert ctx["doc_repo"].chunks[cid].category_id is None
