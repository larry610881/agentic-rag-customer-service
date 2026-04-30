"""BDD: unit/rag/multi_mode_retrieval.feature — Issue #43 Stage 2.7."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.rag.query_rag_use_case import (
    QueryRAGCommand,
    QueryRAGUseCase,
)
from src.domain.rag.value_objects import SearchResult
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeEmbeddingService,
    FakeKbRepo,
    FakeVectorStore,
    make_kb,
    run,
)

scenarios("unit/rag/multi_mode_retrieval.feature")


class _RecordingVectorStore(FakeVectorStore):
    """記錄每次 search 呼叫，方便驗 multi-query 並行展開。"""

    def __init__(self) -> None:
        super().__init__()
        self.search_calls: list[dict] = []

    async def search(
        self, collection, query_vector, limit=5, score_threshold=0.3, filters=None
    ):
        self.search_calls.append(
            {
                "collection": collection,
                "limit": limit,
                "score_threshold": score_threshold,
                "filters": dict(filters or {}),
            }
        )
        return list(self.search_results[:limit])


@pytest.fixture
def ctx():
    return {}


def _seed(ctx, *, tenant_id="T001", kb_id="kb-1", chunks=3):
    kb_repo = FakeKbRepo()
    vs = _RecordingVectorStore()
    embed = FakeEmbeddingService()
    run(kb_repo.save(make_kb(kb_id, tenant_id)))
    vs.search_results = [
        SearchResult(
            id=f"c-{i}",
            score=0.9 - i * 0.1,
            payload={
                "content": f"片段 {i}",
                "tenant_id": tenant_id,
                "document_id": "d1",
                "document_name": "doc",
            },
        )
        for i in range(chunks)
    ]
    use_case = QueryRAGUseCase(
        knowledge_base_repository=kb_repo,
        embedding_service=embed,
        vector_store=vs,
        llm_service=None,
    )
    ctx.update(
        kb_repo=kb_repo,
        vs=vs,
        embed=embed,
        kb_id=kb_id,
        tenant_id=tenant_id,
        use_case=use_case,
    )


@given(parsers.parse('租戶 "{tenant_id}" 的 KB "{kb_id}" 有 {n:d} 筆已 embed 的 chunks'))
def seed_with_n(ctx, tenant_id, kb_id, n):
    _seed(ctx, tenant_id=tenant_id, kb_id=kb_id, chunks=n)


@given(parsers.parse('租戶 "{tenant_id}" 的 KB "{kb_id}" 有已 embed 的 chunks'))
def seed_default(ctx, tenant_id, kb_id):
    _seed(ctx, tenant_id=tenant_id, kb_id=kb_id, chunks=3)


@given("兩條 mode query 命中相同 chunk_id 集合")
def seed_overlap(ctx):
    _seed(ctx, tenant_id="T001", kb_id="kb-1", chunks=3)


@given(parsers.parse('設定 bot_system_prompt 為 "{prompt}"'))
def seed_with_bot(ctx, prompt):
    _seed(ctx, tenant_id="T001", kb_id="kb-1", chunks=3)
    ctx["bot_system_prompt"] = prompt


# ── Mock LLM helpers ────────────────────────────────────────────


def _patched_rewrite(*args, **kwargs):
    raw = args[0] if args else kwargs.get("raw_query", "")
    return f"[rewritten] {raw}"


def _patched_hyde(*args, **kwargs):
    raw = args[0] if args else kwargs.get("raw_query", "")
    return f"[hyde-answer] {raw}"


def _execute(ctx, modes, query, *, bot_system_prompt=""):
    """執行 retrieve()，patch rewrite_query / generate_hyde 避免真打 LLM。"""
    captured: dict = {}

    async def mock_rewrite(raw_query, **kwargs):
        captured["rewrite_kwargs"] = kwargs
        return _patched_rewrite(raw_query)

    async def mock_hyde(raw_query, **kwargs):
        captured["hyde_kwargs"] = kwargs
        return _patched_hyde(raw_query)

    with patch(
        "src.application.rag.query_rag_use_case.rewrite_query",
        side_effect=mock_rewrite,
    ), patch(
        "src.application.rag.query_rag_use_case.generate_hyde",
        side_effect=mock_hyde,
    ):
        try:
            cmd = QueryRAGCommand(
                tenant_id=ctx["tenant_id"],
                kb_id=ctx["kb_id"],
                query=query,
                top_k=10,
                score_threshold=0.0,
                retrieval_modes=list(modes),
                bot_system_prompt=bot_system_prompt,
            )
            ctx["result"] = run(ctx["use_case"].retrieve(cmd))
            ctx["error"] = None
        except Exception as e:
            ctx["result"] = None
            ctx["error"] = e
        ctx["captured"] = captured


@when(parsers.parse('我以 retrieval_modes=["raw"] 查詢 "{query}"'))
def when_raw(ctx, query):
    _execute(ctx, ["raw"], query)


@when(parsers.parse('我以 retrieval_modes=["raw","rewrite"] 查詢 "{query}"'))
def when_raw_rewrite(ctx, query):
    _execute(ctx, ["raw", "rewrite"], query)


@when("執行 multi-mode 檢索")
def when_multi_overlap(ctx):
    _execute(ctx, ["raw", "rewrite"], "退貨")


@when(parsers.parse('我以 retrieval_modes=["hyde"] 查詢 "{query}"'))
def when_hyde(ctx, query):
    _execute(ctx, ["hyde"], query)


@when("我以空 retrieval_modes 查詢")
def when_empty(ctx):
    _execute(ctx, [], "anything")


@when("我以 retrieval_modes=[\"rewrite\"] + 該 bot context 查詢")
def when_rewrite_with_bot(ctx):
    _execute(ctx, ["rewrite"], "查詢", bot_system_prompt=ctx["bot_system_prompt"])


# ── Then assertions ─────────────────────────────────────────────


@then(parsers.parse("應回傳 {n:d} 筆結果"))
def then_n_results(ctx, n):
    assert ctx["error"] is None, ctx["error"]
    assert len(ctx["result"].chunks) == n


@then("mode_queries 應只有 raw 對應原始 query")
def then_only_raw(ctx):
    mq = ctx["result"].mode_queries
    assert set(mq.keys()) == {"raw"}


@then("mode_queries 應包含 raw 與 rewrite 兩個 mode")
def then_raw_and_rewrite(ctx):
    mq = ctx["result"].mode_queries
    assert "raw" in mq and "rewrite" in mq


@then(parsers.parse("vector store 應收到 {n:d} 條搜尋呼叫"))
def then_n_search_calls(ctx, n):
    assert len(ctx["vs"].search_calls) == n


@then("rewrite query 字串可不同於原始 query")
def then_rewrite_diff(ctx):
    mq = ctx["result"].mode_queries
    assert mq["rewrite"].startswith("[rewritten]")


@then("結果應 union by chunk_id（保留最高分）")
def then_union(ctx):
    chunks = ctx["result"].chunks
    # all unique
    sources = ctx["result"].sources
    chunk_ids = [s.chunk_id for s in sources]
    assert len(chunk_ids) == len(set(chunk_ids)), (
        f"duplicate chunk_ids: {chunk_ids}"
    )


@then("結果筆數不應超過 unique chunk 數")
def then_no_dup(ctx):
    sources = ctx["result"].sources
    assert len({s.chunk_id for s in sources}) == len(sources)


@then("mode_queries 應只含 hyde")
def then_only_hyde(ctx):
    mq = ctx["result"].mode_queries
    assert set(mq.keys()) == {"hyde"}


@then("hyde 對應字串可不同於原始 query")
def then_hyde_diff(ctx):
    mq = ctx["result"].mode_queries
    assert mq["hyde"].startswith("[hyde-answer]")


@then("應 raise ValueError")
def then_value_error(ctx):
    assert isinstance(ctx["error"], ValueError), ctx["error"]


@then("rewrite_query helper 應收到該 bot_system_prompt")
def then_rewrite_received_prompt(ctx):
    captured = ctx["captured"]
    assert "rewrite_kwargs" in captured, "rewrite_query never called"
    assert captured["rewrite_kwargs"].get("bot_system_prompt") == ctx["bot_system_prompt"]
