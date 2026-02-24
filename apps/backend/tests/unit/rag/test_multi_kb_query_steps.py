"""多知識庫 RAG 查詢 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.domain.rag.value_objects import LLMResult, SearchResult, TokenUsage

scenarios("unit/rag/multi_kb_query.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_kb(kb_id, tenant_id):
    return SimpleNamespace(
        id=SimpleNamespace(value=kb_id),
        tenant_id=tenant_id,
        name=f"KB {kb_id}",
        description="Test",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _setup_use_case(context, kb_ids, tenant_id, search_results_map):
    """Set up use case with per-collection search results."""
    mock_kb_repo = AsyncMock()
    mock_kb_repo.find_by_id = AsyncMock(
        side_effect=lambda kid: _make_kb(kid, tenant_id)
    )

    mock_embedding = AsyncMock()
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 1536)

    mock_vector_store = AsyncMock()

    def _search(collection, query_vector, limit, score_threshold, filters):
        return search_results_map.get(collection, [])

    mock_vector_store.search = AsyncMock(side_effect=_search)

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            text="根據知識庫：退貨政策為30天內可退貨",
            usage=TokenUsage.zero("fake"),
        )
    )

    use_case = QueryRAGUseCase(
        knowledge_base_repository=mock_kb_repo,
        embedding_service=mock_embedding,
        vector_store=mock_vector_store,
        llm_service=mock_llm,
    )

    context["use_case"] = use_case
    context["mock_vector_store"] = mock_vector_store
    context["tenant_id"] = tenant_id
    context["kb_ids"] = kb_ids


@given(parsers.parse('租戶 "{tenant_id}" 有知識庫列表 "{kb_ids_str}"'))
def tenant_has_kbs(context, tenant_id, kb_ids_str):
    context["tenant_id"] = tenant_id
    context["_kb_ids"] = [k.strip() for k in kb_ids_str.split(",")]


@given("所有知識庫都有相關文件")
def all_kbs_have_docs(context):
    kb_ids = context["_kb_ids"]
    search_results_map = {}
    for i, kb_id in enumerate(kb_ids):
        search_results_map[f"kb_{kb_id}"] = [
            SearchResult(
                id=f"chunk-{i + 1}",
                score=0.9 - i * 0.2,
                payload={
                    "content": f"知識庫 {kb_id} 的退貨政策內容",
                    "document_name": f"政策_{kb_id}.txt",
                    "tenant_id": context["tenant_id"],
                },
            ),
        ]
    _setup_use_case(
        context, kb_ids, context["tenant_id"], search_results_map
    )


@when(parsers.parse('對知識庫 "{kb_ids_str}" 查詢 "{query}"'))
def query_multi_kb(context, kb_ids_str, query):
    kb_ids = [k.strip() for k in kb_ids_str.split(",")]
    context["result"] = _run(
        context["use_case"].execute(
            QueryRAGCommand(
                tenant_id=context["tenant_id"],
                kb_id=kb_ids[0],
                query=query,
                kb_ids=kb_ids,
            )
        )
    )


@then("應合併兩個知識庫的搜尋結果")
def verify_merged_results(context):
    assert context["mock_vector_store"].search.call_count == 2
    assert len(context["result"].sources) >= 2


@then("結果應按相關度排序")
def verify_sorted_by_score(context):
    scores = [s.score for s in context["result"].sources]
    assert scores == sorted(scores, reverse=True)


@then(parsers.parse('應只搜尋 "{kb_id}" 的結果'))
def verify_single_kb_search(context, kb_id):
    assert context["mock_vector_store"].search.call_count == 1
    call_args = context["mock_vector_store"].search.call_args
    assert call_args.kwargs["collection"] == f"kb_{kb_id}"
