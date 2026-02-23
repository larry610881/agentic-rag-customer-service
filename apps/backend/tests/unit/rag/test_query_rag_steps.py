"""RAG 查詢 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.domain.rag.value_objects import LLMResult, SearchResult, TokenUsage
from src.domain.shared.exceptions import EntityNotFoundError, NoRelevantKnowledgeError

scenarios("unit/rag/query_rag.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_kb(kb_id: str, tenant_id: str):
    return SimpleNamespace(
        id=SimpleNamespace(value=kb_id),
        tenant_id=tenant_id,
        name="Test KB",
        description="Test",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _setup_use_case(context, kb_id, tenant_id, search_results, kb_exists=True):
    mock_kb_repo = AsyncMock()
    if kb_exists:
        mock_kb_repo.find_by_id = AsyncMock(
            return_value=_make_kb(kb_id, tenant_id)
        )
    else:
        mock_kb_repo.find_by_id = AsyncMock(return_value=None)

    mock_embedding = AsyncMock()
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 1536)

    mock_vector_store = AsyncMock()
    mock_vector_store.search = AsyncMock(return_value=search_results)

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
    context["mock_kb_repo"] = mock_kb_repo
    context["mock_embedding"] = mock_embedding
    context["mock_vector_store"] = mock_vector_store
    context["mock_llm"] = mock_llm
    context["tenant_id"] = tenant_id
    context["kb_id"] = kb_id


@given('知識庫 "kb-001" 存在且屬於 tenant "tenant-001"')
def kb_exists(context):
    context["_kb_id"] = "kb-001"
    context["_tenant_id"] = "tenant-001"


@given("向量搜尋回傳 2 筆相關結果")
def setup_2_results(context):
    results = [
        SearchResult(
            id="chunk-1",
            score=0.9,
            payload={
                "content": "退貨政策：30天內可退貨，需保持商品完整",
                "document_name": "退貨政策.txt",
                "tenant_id": "tenant-001",
            },
        ),
        SearchResult(
            id="chunk-2",
            score=0.8,
            payload={
                "content": "退貨流程：請聯繫客服取得退貨單號",
                "document_name": "退貨流程.txt",
                "tenant_id": "tenant-001",
            },
        ),
    ]
    _setup_use_case(context, context["_kb_id"], context["_tenant_id"], results)


@given("向量搜尋回傳空結果")
def setup_empty_results(context):
    _setup_use_case(context, context["_kb_id"], context["_tenant_id"], [])


@given("向量搜尋回傳 1 筆相關結果")
def setup_1_result(context):
    results = [
        SearchResult(
            id="chunk-1",
            score=0.85,
            payload={
                "content": "退貨政策：30天內可退貨",
                "document_name": "退貨政策.txt",
                "tenant_id": "tenant-001",
            },
        ),
    ]
    _setup_use_case(context, context["_kb_id"], context["_tenant_id"], results)


@given('知識庫 "kb-999" 不存在')
def kb_not_exists(context):
    _setup_use_case(context, "kb-999", "tenant-001", [], kb_exists=False)


@when('執行 RAG 查詢 "退貨政策是什麼"')
def do_query(context):
    try:
        context["result"] = _run(
            context["use_case"].execute(
                QueryRAGCommand(
                    tenant_id=context["tenant_id"],
                    kb_id=context["kb_id"],
                    query="退貨政策是什麼",
                )
            )
        )
    except (NoRelevantKnowledgeError, EntityNotFoundError) as e:
        context["error"] = e


@when('執行 RAG 查詢 "不存在的主題"')
def do_query_no_results(context):
    try:
        context["result"] = _run(
            context["use_case"].execute(
                QueryRAGCommand(
                    tenant_id=context["tenant_id"],
                    kb_id=context["kb_id"],
                    query="不存在的主題",
                )
            )
        )
    except (NoRelevantKnowledgeError, EntityNotFoundError) as e:
        context["error"] = e


@when('執行 RAG 查詢 "任何問題" 到知識庫 "kb-999"')
def do_query_kb_not_found(context):
    try:
        context["result"] = _run(
            context["use_case"].execute(
                QueryRAGCommand(
                    tenant_id=context["tenant_id"],
                    kb_id="kb-999",
                    query="任何問題",
                )
            )
        )
    except (NoRelevantKnowledgeError, EntityNotFoundError) as e:
        context["error"] = e


@then("應回傳包含回答的 RAGResponse")
def verify_rag_response(context):
    result = context["result"]
    assert result.answer is not None
    assert len(result.answer) > 0


@then('回答應包含 "根據知識庫"')
def verify_answer_content(context):
    assert "根據知識庫" in context["result"].answer


@then("來源列表應包含 2 筆引用")
def verify_2_sources(context):
    assert len(context["result"].sources) == 2


@then("每筆引用應包含文件名稱和內容片段")
def verify_source_fields(context):
    for source in context["result"].sources:
        assert source.document_name != ""
        assert source.content_snippet != ""
        assert source.score > 0
        assert source.chunk_id != ""


@then("應拋出 NoRelevantKnowledgeError")
def verify_no_knowledge_error(context):
    assert isinstance(context["error"], NoRelevantKnowledgeError)


@then('向量搜尋應使用 tenant_id "tenant-001" 過濾')
def verify_tenant_filter(context):
    call_args = context["mock_vector_store"].search.call_args
    assert call_args.kwargs["filters"] == {"tenant_id": "tenant-001"}


@then("應拋出 EntityNotFoundError")
def verify_entity_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)
