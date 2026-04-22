"""BDD: unit/knowledge/list_kb_chunks.feature"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.list_kb_chunks_use_case import (
    ListKbChunksQuery,
    ListKbChunksUseCase,
)
from src.domain.shared.exceptions import EntityNotFoundError
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeDocumentRepo,
    FakeKbRepo,
    make_chunk,
    make_doc,
    make_kb,
    run,
)

scenarios("unit/knowledge/list_kb_chunks.feature")


@pytest.fixture
def ctx():
    return {}


@given(parsers.parse('租戶 "{tenant_id}" 的 KB "{kb_id}" 有 {n:d} 個 chunks'))
def seed_n(ctx, tenant_id, kb_id, n):
    doc_repo = FakeDocumentRepo()
    kb_repo = FakeKbRepo()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    run(doc_repo.save(make_doc("doc-1", kb_id, tenant_id)))
    run(
        doc_repo.save_chunks(
            [make_chunk(f"c-{i}", "doc-1", tenant_id) for i in range(n)]
        )
    )
    ctx.update(doc_repo=doc_repo, kb_repo=kb_repo, kb_id=kb_id, tenant_id=tenant_id)


@given(
    parsers.parse(
        '租戶 "{tenant_id}" 的 KB "{kb_id}" 有 chunks：{a:d} 筆屬 category "{cat_a}"、{b:d} 筆屬 category "{cat_b}"、{c:d} 筆未分類'
    )
)
def seed_categorized(ctx, tenant_id, kb_id, a, cat_a, b, cat_b, c):
    doc_repo = FakeDocumentRepo()
    kb_repo = FakeKbRepo()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    run(doc_repo.save(make_doc("doc-1", kb_id, tenant_id)))
    chunks = []
    idx = 0
    for _ in range(a):
        chunks.append(make_chunk(f"c-{idx}", "doc-1", tenant_id, category_id=cat_a))
        idx += 1
    for _ in range(b):
        chunks.append(make_chunk(f"c-{idx}", "doc-1", tenant_id, category_id=cat_b))
        idx += 1
    for _ in range(c):
        chunks.append(make_chunk(f"c-{idx}", "doc-1", tenant_id))
        idx += 1
    run(doc_repo.save_chunks(chunks))
    ctx.update(doc_repo=doc_repo, kb_repo=kb_repo, kb_id=kb_id, tenant_id=tenant_id)


@given(parsers.parse('租戶 "{tenant_id}" 擁有 KB "{kb_id}"'))
def seed_kb_only(ctx, tenant_id, kb_id):
    seed_n(ctx, tenant_id, kb_id, 0)


def _run_list(ctx, *, tenant, kb_id, page=1, page_size=50, category_id=None):
    uc = ListKbChunksUseCase(
        document_repo=ctx["doc_repo"], kb_repo=ctx["kb_repo"]
    )
    try:
        ctx["result"] = run(
            uc.execute(
                ListKbChunksQuery(
                    kb_id=kb_id,
                    tenant_id=tenant,
                    page=page,
                    page_size=page_size,
                    category_id=category_id,
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e
        ctx["result"] = None


@when(
    parsers.parse(
        '我以 tenant "{tenant}" 身分呼叫 list_kb_chunks(kb_id="{kb_id}", page={page:d}, page_size={page_size:d})'
    )
)
def when_list_paginated(ctx, tenant, kb_id, page, page_size):
    _run_list(ctx, tenant=tenant, kb_id=kb_id, page=page, page_size=page_size)


@when(
    parsers.parse(
        '我呼叫 list_kb_chunks(kb_id="{kb_id}", category_id="{cat}")'
    )
)
def when_list_cat(ctx, kb_id, cat):
    _run_list(ctx, tenant=ctx["tenant_id"], kb_id=kb_id, category_id=cat)


@when(parsers.parse('我以 tenant "{tenant}" 身分呼叫 list_kb_chunks(kb_id="{kb_id}")'))
def when_list_basic(ctx, tenant, kb_id):
    _run_list(ctx, tenant=tenant, kb_id=kb_id)


@then(parsers.parse("回傳 items 應為 {n:d} 筆"))
def then_items_n(ctx, n):
    assert ctx["error"] is None
    assert len(ctx["result"].items) == n


@then(parsers.parse("回傳 total 應為 {n:d}"))
def then_total(ctx, n):
    assert ctx["result"].total == n


@then(parsers.parse("回傳 page 應為 {n:d}"))
def then_page(ctx, n):
    assert ctx["result"].page == n


@then(parsers.parse('回傳 items 應全部屬於 category "{cat}"'))
def then_all_cat(ctx, cat):
    assert all(c.category_id == cat for c in ctx["result"].items)


@then("應拋出 EntityNotFoundError（回 404 防枚舉）")
def then_not_found(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)


@then("回傳 items 應為空陣列")
def then_empty(ctx):
    assert ctx["result"].items == []
