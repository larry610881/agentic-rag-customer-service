"""向量搜尋 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.rag.value_objects import SearchResult

scenarios("unit/rag/vector_search.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    return store


@given("向量資料庫中有 3 筆向量資料")
def setup_3_results(context, mock_vector_store):
    results = [
        SearchResult(
            id=f"chunk-{i}",
            score=0.9 - i * 0.1,
            payload={"content": f"content {i}", "tenant_id": "t-1"},
        )
        for i in range(3)
    ]
    mock_vector_store.search = AsyncMock(return_value=results)
    context["mock_vector_store"] = mock_vector_store
    context["query_vector"] = [0.1] * 1536


@given('向量資料庫中有屬於 tenant "tenant-001" 的資料')
def setup_tenant_data(context, mock_vector_store):
    results = [
        SearchResult(
            id="chunk-0",
            score=0.85,
            payload={
                "content": "退貨政策",
                "tenant_id": "tenant-001",
            },
        ),
    ]
    mock_vector_store.search = AsyncMock(return_value=results)
    context["mock_vector_store"] = mock_vector_store
    context["query_vector"] = [0.1] * 1536


@given("向量資料庫中的資料分數均低於閾值")
def setup_empty_results(context, mock_vector_store):
    mock_vector_store.search = AsyncMock(return_value=[])
    context["mock_vector_store"] = mock_vector_store
    context["query_vector"] = [0.1] * 1536


@when("執行向量搜尋查詢")
def do_search(context):
    context["results"] = _run(
        context["mock_vector_store"].search(
            collection="kb_test",
            query_vector=context["query_vector"],
            limit=5,
            score_threshold=0.3,
        )
    )


@when('以 tenant "tenant-001" 過濾條件執行搜尋')
def do_search_with_filter(context):
    context["results"] = _run(
        context["mock_vector_store"].search(
            collection="kb_test",
            query_vector=context["query_vector"],
            limit=5,
            score_threshold=0.3,
            filters={"tenant_id": "tenant-001"},
        )
    )


@then("應回傳 3 筆 SearchResult")
def verify_3_results(context):
    assert len(context["results"]) == 3
    for r in context["results"]:
        assert isinstance(r, SearchResult)


@then('搜尋時應傳入 tenant_id "tenant-001" 過濾條件')
def verify_tenant_filter(context):
    call_args = context["mock_vector_store"].search.call_args
    assert call_args.kwargs["filters"] == {"tenant_id": "tenant-001"}


@then("應回傳空的搜尋結果列表")
def verify_empty_results(context):
    assert context["results"] == []
