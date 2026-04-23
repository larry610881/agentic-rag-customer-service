"""Token Usage 追蹤 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from langchain_core.messages import AIMessage

from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.rag.value_objects import LLMResult, SearchResult, TokenUsage
from src.domain.usage.repository import UsageRepository
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

    # S-KB-Followup.2: 原測試 QueryRAGUseCase.execute()，已隨 pure RAG legacy 清除。
    # context 裡保留 mock_* 但不建 use_case。


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


# --- Scenario: RecordUsageUseCase 自動補算 estimated_cost ---


@given("一筆 TokenUsage 的 estimated_cost 為 0 但有 tokens")
def setup_zero_cost_usage(context):
    context["mock_repo"] = AsyncMock(spec=UsageRepository)
    context["use_case"] = RecordUsageUseCase(
        usage_repository=context["mock_repo"],
    )
    # ReAct 路徑產出的 TokenUsage — cost=0 但 tokens 有值
    context["usage"] = TokenUsage(
        model="gpt-5.1-2025-11-13",
        input_tokens=55764,
        output_tokens=479,
        estimated_cost=0.0,
    )


@when("執行 RecordUsageUseCase")
def run_record_usage(context):
    _run(
        context["use_case"].execute(
            tenant_id="tenant-001",
            request_type="rag",  # Token-Gov: 白名單需 UsageCategory enum value
            usage=context["usage"],
            bot_id="bot-001",
        )
    )


@then("儲存的 UsageRecord 的 estimated_cost 應大於 0")
def verify_cost_filled(context):
    saved = context["mock_repo"].save.call_args[0][0]
    assert saved.estimated_cost > 0, f"expected > 0, got {saved.estimated_cost}"


# --- Scenario: RecordUsageUseCase 不覆蓋已有的 estimated_cost ---


@given("一筆 TokenUsage 已包含正確的 estimated_cost")
def setup_existing_cost_usage(context):
    context["mock_repo"] = AsyncMock(spec=UsageRepository)
    context["use_case"] = RecordUsageUseCase(
        usage_repository=context["mock_repo"],
    )
    context["usage"] = TokenUsage(
        model="gpt-5.1",
        input_tokens=1000,
        output_tokens=500,
        estimated_cost=0.00625,
    )
    context["original_cost"] = 0.00625


@then("儲存的 UsageRecord 的 estimated_cost 應等於原始值")
def verify_cost_preserved(context):
    saved = context["mock_repo"].save.call_args[0][0]
    assert abs(saved.estimated_cost - context["original_cost"]) < 1e-10


# --- Scenario: TokenUsage 支援累加 ---


@given("兩個 TokenUsage 物件")
def setup_two_usages(context):
    context["usage_a"] = TokenUsage(
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.001,
    )
    context["usage_b"] = TokenUsage(
        model="test-model",
        input_tokens=200,
        output_tokens=100,
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


# --- Scenario: extract_usage_from_accumulated 保留 cache tokens ---


@given("一個包含 cache tokens 的 accumulated usage dict")
def setup_accumulated_with_cache(context):
    context["acc"] = {
        "model": "claude-sonnet-4-6",
        "input_tokens": 1000,
        "output_tokens": 200,
        "total_tokens": 1700,
        "estimated_cost": 0.01,
        "cache_read_tokens": 400,
        "cache_creation_tokens": 100,
    }


@when("用 extract_usage_from_accumulated 轉換")
def run_extract_accumulated(context):
    from src.infrastructure.langgraph.usage import extract_usage_from_accumulated

    context["result"] = extract_usage_from_accumulated(context["acc"])


@then("結果應包含 cache_read_tokens 和 cache_creation_tokens")
def verify_accumulated_cache(context):
    result = context["result"]
    assert result.cache_read_tokens == 400
    assert result.cache_creation_tokens == 100
    assert result.input_tokens == 1000
    assert result.output_tokens == 200


# --- Scenario: OpenAI 風格 — input_tokens 包含 cached ---


@given("一組 OpenAI 風格的 AIMessage 其 input_tokens 包含 cached")
def setup_openai_messages(context):
    from unittest.mock import MagicMock

    msg = MagicMock(spec=AIMessage)
    # OpenAI: input_tokens=1000 (includes 300 cached), output_tokens=200
    msg.usage_metadata = {
        "input_tokens": 1000,
        "output_tokens": 200,
        "input_token_details": {"cached": 300},
    }
    msg.response_metadata = {"model_name": "gpt-5.1"}
    context["messages"] = [msg]


@when("用 extract_usage_from_langchain_messages 提取")
def run_extract_langchain(context):
    from src.infrastructure.langgraph.usage import (
        extract_usage_from_langchain_messages,
    )

    context["result"] = extract_usage_from_langchain_messages(context["messages"])


@then("input_tokens 應已扣除 cached 避免重複計算")
def verify_openai_input_normalized(context):
    # 1000 (raw) - 300 (cached) = 700 (non-cached input)
    assert context["result"].input_tokens == 700


@then("cache_read_tokens 應等於 cached 數量")
def verify_openai_cache_read(context):
    assert context["result"].cache_read_tokens == 300


# --- Scenario: Anthropic 風格 — input_tokens 不含 cache ---


@given("一組 Anthropic 風格的 AIMessage 其 input_tokens 不含 cache")
def setup_anthropic_messages(context):
    from unittest.mock import MagicMock

    msg = MagicMock(spec=AIMessage)
    # Anthropic: input_tokens=500 (excludes cache), cache_read=300, cache_creation=100
    msg.usage_metadata = {
        "input_tokens": 500,
        "output_tokens": 200,
        "input_token_details": {"cache_read": 300, "cache_creation": 100},
    }
    msg.response_metadata = {"model_name": "claude-sonnet-4-6"}
    context["messages"] = [msg]


@when("用 extract_usage_from_langchain_messages 提取", target_fixture="result")
def run_extract_langchain_anthropic(context):
    from src.infrastructure.langgraph.usage import (
        extract_usage_from_langchain_messages,
    )

    context["result"] = extract_usage_from_langchain_messages(context["messages"])


@then("input_tokens 應維持原始值不扣除")
def verify_anthropic_input_preserved(context):
    assert context["result"].input_tokens == 500


@then("cache_read_tokens 應等於 cache_read 數量")
def verify_anthropic_cache_read(context):
    assert context["result"].cache_read_tokens == 300


@then("cache_creation_tokens 應等於 cache_creation 數量")
def verify_anthropic_cache_creation(context):
    assert context["result"].cache_creation_tokens == 100


# --- Scenario: RecordUsageUseCase fallback 成本計算含 cache tokens ---


@given("一筆含 cache tokens 但 estimated_cost 為 0 的 TokenUsage")
def setup_cache_usage_zero_cost(context):
    context["mock_repo"] = AsyncMock(spec=UsageRepository)
    context["use_case"] = RecordUsageUseCase(
        usage_repository=context["mock_repo"],
    )
    # Anthropic 風格：input=500(非快取), cache_read=300, cache_creation=100
    context["usage"] = TokenUsage(
        model="claude-sonnet-4-6",
        input_tokens=500,
        output_tokens=200,
        estimated_cost=0.0,
        cache_read_tokens=300,
        cache_creation_tokens=100,
    )
    # 計算只含 input+output 的基準成本（不含 cache）
    from src.domain.rag.pricing import calculate_usage

    base = calculate_usage(
        model="claude-sonnet-4-6",
        input_tokens=500,
        output_tokens=200,
        pricing={"claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_creation": 3.75}},
    )
    context["base_cost"] = base.estimated_cost


@then("儲存的成本應高於只算 input+output 的成本")
def verify_fallback_includes_cache(context):
    saved = context["mock_repo"].save.call_args[0][0]
    base_cost = context["base_cost"]
    assert saved.estimated_cost > base_cost, (
        f"expected > {base_cost}, got {saved.estimated_cost} "
        f"(cache tokens should add to cost)"
    )
