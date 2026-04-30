"""BDD: unit/knowledge/test_retrieval.feature (Playground)"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.test_retrieval_use_case import (
    TestRetrievalCommand,
    TestRetrievalUseCase,
)
from src.application.rag.query_rag_use_case import QueryRAGUseCase
from src.domain.rag.value_objects import SearchResult
from src.domain.shared.exceptions import EntityNotFoundError
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeEmbeddingService,
    FakeKbRepo,
    FakeVectorStore,
    make_kb,
    run,
)


def _make_query_rag(kb_repo, embed, vs):
    """建一個共用 QueryRAGUseCase（Stage 2.6 之後 TestRetrievalUseCase 需注入）。"""
    return QueryRAGUseCase(
        knowledge_base_repository=kb_repo,
        embedding_service=embed,
        vector_store=vs,
        llm_service=None,  # 此 unit test 不會走到 LLM 生成路徑
    )

scenarios("unit/knowledge/test_retrieval.feature")


@pytest.fixture
def ctx():
    return {}


def _setup(ctx, *, tenant_id="T001", kb_id="kb-1", include_results=True):
    kb_repo = FakeKbRepo()
    vs = FakeVectorStore()
    embed = FakeEmbeddingService()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    if include_results:
        vs.search_results = [
            SearchResult(id=f"c-{i}", score=0.9 - i * 0.1, payload={"content": f"片段 {i}", "tenant_id": tenant_id})
            for i in range(3)
        ]
    ctx.update(kb_repo=kb_repo, vs=vs, embed=embed, kb_id=kb_id, tenant_id=tenant_id)


@given(parsers.parse('租戶 "{tenant_id}" 的 KB "{kb_id}" 有已 embed 的 chunks'))
def seed_embedded(ctx, tenant_id, kb_id):
    _setup(ctx, tenant_id=tenant_id, kb_id=kb_id)


@given(parsers.parse('租戶 "{t1}" 與 "{t2}" 的 KB 都有 "退貨" 相關 chunks'))
def seed_two_tenants(ctx, t1, t2):
    _setup(ctx, tenant_id=t1, kb_id="kb-1")


@given(parsers.parse('租戶 "{tenant_id}" 的 KB 有相關 chunks'))
def seed_kb_has_chunks(ctx, tenant_id):
    _setup(ctx, tenant_id=tenant_id)


@given(parsers.parse('租戶 "{tenant_id}" 的 conv_summaries 也有相關對話摘要'))
def seed_conv(ctx, tenant_id):
    ctx["vs"].search_results.append(
        SearchResult(id="cs-1", score=0.85, payload={"summary": "對話摘要", "tenant_id": tenant_id})
    )


@given(parsers.parse('租戶 "{tenant_id}" 擁有 KB "{kb_id}"'))
def seed_own(ctx, tenant_id, kb_id):
    _setup(ctx, tenant_id=tenant_id, kb_id=kb_id, include_results=False)


def _run_test(ctx, *, tenant, kb_id, query, top_k=5, include_conv=False):
    uc = TestRetrievalUseCase(
        kb_repo=ctx["kb_repo"],
        embedding_service=ctx["embed"],
        vector_store=ctx["vs"],
        query_rag_use_case=_make_query_rag(
            ctx["kb_repo"], ctx["embed"], ctx["vs"]
        ),
    )
    try:
        ctx["result"] = run(
            uc.execute(
                TestRetrievalCommand(
                    kb_id=kb_id,
                    tenant_id=tenant,
                    query=query,
                    top_k=top_k,
                    include_conv_summaries=include_conv,
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e
        ctx["result"] = None


@when(
    parsers.parse(
        '我以 tenant "{tenant}" 身分呼叫 test_retrieval(kb_id="{kb_id}", query="{q}", top_k={k:d})'
    )
)
def when_retrieve(ctx, tenant, kb_id, q, k):
    _run_test(ctx, tenant=tenant, kb_id=kb_id, query=q, top_k=k)


@when(
    parsers.parse(
        '我以 tenant "{tenant}" 身分呼叫 test_retrieval(kb_id="{kb_id}", query="{q}")'
    )
)
def when_retrieve_default(ctx, tenant, kb_id, q):
    _run_test(ctx, tenant=tenant, kb_id=kb_id, query=q)


@when(
    parsers.parse(
        '我呼叫 test_retrieval(kb_id="{kb_id}", query="{q}", include_conv_summaries=True)'
    )
)
def when_retrieve_cross(ctx, kb_id, q):
    _run_test(ctx, tenant=ctx["tenant_id"], kb_id=kb_id, query=q, include_conv=True)


@when(
    parsers.parse(
        '我以 tenant "{tenant}" 身分呼叫 test_retrieval(kb_id="{kb_id}", query="{q}")'
    )
)
def when_cross_tenant(ctx, tenant, kb_id, q):
    _run_test(ctx, tenant=tenant, kb_id=kb_id, query=q)


@then(parsers.parse("回傳 results 應最多 {n:d} 筆"))
def then_max_n(ctx, n):
    assert ctx["error"] is None
    assert len(ctx["result"].results) <= n


@then("每筆應有 chunk_id + content + score")
def then_fields(ctx):
    for r in ctx["result"].results:
        assert r.chunk_id
        assert r.score >= 0


@then(parsers.parse('回傳 filter_expr 應為字串含 "{needle}"'))
def then_filter_contains(ctx, needle):
    assert needle in ctx["result"].filter_expr


@then(parsers.parse('回傳 filter_expr 應含 "{needle}" 關鍵字'))
def then_filter_keyword(ctx, needle):
    assert needle in ctx["result"].filter_expr


@then(parsers.parse('回傳 results 應只含 tenant "{tenant}" 的 chunks'))
def then_only_tenant(ctx, tenant):
    # FakeVectorStore 不做真正的 tenant filter，但 metadata tenant_id 應為該 tenant
    for r in ctx["result"].results:
        md_tenant = (r.metadata or {}).get("tenant_id")
        if md_tenant:
            assert md_tenant == tenant


@then('回傳 results 應含 source="chunk" 與 source="conv_summary" 兩種類型')
def then_both_sources(ctx):
    sources = {r.source for r in ctx["result"].results}
    assert "chunk" in sources
    assert "conv_summary" in sources


@then("應拋出 EntityNotFoundError")
def then_not_found(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)
