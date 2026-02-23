"""Token Usage 追蹤 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.domain.rag.value_objects import LLMResult, SearchResult, TokenUsage
from src.infrastructure.llm.fake_llm_service import FakeLLMService

scenarios("unit/usage/token_usage.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Scenario: RAG 查詢結果包含 token 使用量 ---


@given("知識庫已設定且有搜尋結果")
def setup_rag(context):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    mock_kb_repo = AsyncMock()
    mock_kb_repo.find_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=SimpleNamespace(value="kb-001"),
            tenant_id="tenant-001",
            name="Test KB",
            description="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    mock_embedding = AsyncMock()
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 1536)

    mock_vector_store = AsyncMock()
    mock_vector_store.search = AsyncMock(
        return_value=[
            SearchResult(
                id="chunk-1",
                score=0.9,
                payload={
                    "content": "退貨政策：30天內可退貨",
                    "document_name": "退貨政策.txt",
                    "tenant_id": "tenant-001",
                },
            ),
        ]
    )

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            text="根據知識庫：退貨政策為30天內可退貨",
            usage=TokenUsage.zero("fake"),
        )
    )

    context["use_case"] = QueryRAGUseCase(
        knowledge_base_repository=mock_kb_repo,
        embedding_service=mock_embedding,
        vector_store=mock_vector_store,
        llm_service=mock_llm,
    )


@when("執行 RAG 查詢")
def do_rag_query(context):
    context["result"] = _run(
        context["use_case"].execute(
            QueryRAGCommand(
                tenant_id="tenant-001",
                kb_id="kb-001",
                query="退貨政策是什麼",
            )
        )
    )


@then("RAGResponse 應包含 usage 欄位")
def verify_usage_exists(context):
    assert context["result"].usage is not None


@then('usage 的 model 應為 "fake"')
def verify_usage_model(context):
    assert context["result"].usage.model == "fake"


# --- Scenario: FakeLLM 回傳零 usage ---


@given("使用 FakeLLMService")
def setup_fake_llm(context):
    context["llm"] = FakeLLMService()


@when("呼叫 generate 生成回答")
def do_generate(context):
    context["llm_result"] = _run(
        context["llm"].generate(
            system_prompt="你是客服助手",
            user_message="退貨政策是什麼？",
            context="退貨政策：30天內可退貨",
        )
    )


@then("回傳的 LLMResult 應包含 TokenUsage")
def verify_llm_result_has_usage(context):
    assert context["llm_result"].usage is not None
    assert isinstance(context["llm_result"].usage, TokenUsage)


@then("usage 的 total_tokens 應為 0")
def verify_zero_tokens(context):
    assert context["llm_result"].usage.total_tokens == 0


# --- Scenario: TokenUsage 支援累加 ---


@given("兩個 TokenUsage 物件")
def setup_two_usages(context):
    context["usage_a"] = TokenUsage(
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost=0.001,
    )
    context["usage_b"] = TokenUsage(
        model="test-model",
        input_tokens=200,
        output_tokens=100,
        total_tokens=300,
        estimated_cost=0.002,
    )


@when("將兩個 usage 相加")
def add_usages(context):
    context["sum_usage"] = context["usage_a"] + context["usage_b"]


@then("結果的 input_tokens 應為兩者之和")
def verify_input_sum(context):
    assert context["sum_usage"].input_tokens == 300


@then("結果的 output_tokens 應為兩者之和")
def verify_output_sum(context):
    assert context["sum_usage"].output_tokens == 150


@then("結果的 estimated_cost 應為兩者之和")
def verify_cost_sum(context):
    assert abs(context["sum_usage"].estimated_cost - 0.003) < 1e-10
