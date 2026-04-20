"""Token-Gov.0 — Token 追蹤完整性 5 條漏網路徑修復後驗證 BDD Steps"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.intent_classifier import IntentClassifier
from src.application.knowledge.classify_kb_use_case import ClassifyKbUseCase
from src.domain.knowledge.entity import Chunk, ChunkId
from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.domain.usage.category import UsageCategory
from src.infrastructure.context.llm_chunk_context_service import (
    LLMChunkContextService,
)
from src.infrastructure.rag.llm_reranker import llm_rerank

scenarios("unit/usage/usage_tracking_audit.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# ════════════════════════════════════════════════════════════════
# Scenario 1: Contextual Retrieval token 累計
# ════════════════════════════════════════════════════════════════


@given(parsers.parse(
    "LLMChunkContextService 配置好 mock call_llm 回傳 input={inp:d} output={out:d}"
))
def setup_context_service(context, inp, out):
    context["ctx_input"] = inp
    context["ctx_output"] = out
    context["ctx_service"] = LLMChunkContextService(api_key_resolver=None)


@given(parsers.parse(
    '文件內容 "{doc_content}" 與 {n:d} 個 chunk'
))
def setup_document_chunks(context, doc_content, n):
    context["doc_content"] = doc_content
    context["chunks"] = [
        Chunk(
            id=ChunkId(value=f"c-{i}"),
            document_id="d-1",
            tenant_id="tenant-1",
            content=f"chunk content {i}",
            chunk_index=i,
        )
        for i in range(n)
    ]


@when("呼叫 generate_contexts")
def call_generate_contexts(context):
    fake_result = SimpleNamespace(
        text="片段位於文件開頭",
        input_tokens=context["ctx_input"],
        output_tokens=context["ctx_output"],
    )

    async def fake_call_llm(*args, **kwargs):
        return fake_result

    with patch(
        "src.infrastructure.context.llm_chunk_context_service.call_llm",
        side_effect=fake_call_llm,
    ):
        _run(context["ctx_service"].generate_contexts(
            document_content=context["doc_content"],
            chunks=context["chunks"],
            model="anthropic:claude-haiku-4-5-20251001",
        ))


@then(parsers.parse("last_input_tokens 應為 {n:d}"))
def verify_ctx_input_tokens(context, n):
    assert context["ctx_service"].last_input_tokens == n


@then(parsers.parse("last_output_tokens 應為 {n:d}"))
def verify_ctx_output_tokens(context, n):
    assert context["ctx_service"].last_output_tokens == n


@then("last_model 不應為空")
def verify_ctx_model(context):
    assert context["ctx_service"].last_model != ""


# ════════════════════════════════════════════════════════════════
# Scenario 2: LLM Reranker
# ════════════════════════════════════════════════════════════════


@given(parsers.parse(
    "llm_rerank 配置好 mock anthropic 回傳 input={inp:d} output={out:d} cache_read={cache:d}"  # noqa: E501
))
def setup_rerank_anthropic(context, inp, out, cache):
    context["rerank_input"] = inp
    context["rerank_output"] = out
    context["rerank_cache"] = cache


@given(parsers.parse(
    '注入 mock RecordUsageUseCase + tenant_id="{tid}"'
))
def setup_rerank_record_usage(context, tid):
    mock_record = AsyncMock()
    mock_record.execute = AsyncMock()
    context["mock_record_usage"] = mock_record
    context["tenant_id"] = tid


@when(parsers.parse(
    "呼叫 llm_rerank 重排 {n:d} 個 chunks 取 top {k:d}"
))
def call_llm_rerank(context, n, k):
    chunks = [{"content": f"chunk content {i}", "_idx": i} for i in range(n)]

    rerank_json = (
        '[{"index": 0, "score": 9}, '
        '{"index": 1, "score": 8}, '
        '{"index": 2, "score": 7}]'
    )
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(text=rerank_json)],
        usage=SimpleNamespace(
            input_tokens=context["rerank_input"],
            output_tokens=context["rerank_output"],
            cache_read_input_tokens=context["rerank_cache"],
            cache_creation_input_tokens=0,
        ),
    )

    mock_messages = MagicMock()
    mock_messages.create = AsyncMock(return_value=fake_response)
    mock_client = MagicMock()
    mock_client.messages = mock_messages

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        _run(llm_rerank(
            query="test query",
            chunks=chunks,
            model="claude-haiku-4-5-20251001",
            top_k=k,
            api_key="test-key",
            record_usage=context["mock_record_usage"],
            tenant_id=context["tenant_id"],
        ))


@then(parsers.parse("RecordUsageUseCase.execute 應被呼叫 {n:d} 次"))
def verify_record_usage_called(context, n):
    assert context["mock_record_usage"].execute.call_count == n


@then(parsers.parse('該 call 的 request_type 應為 "{cat}"'))
def verify_record_usage_category(context, cat):
    call_args = context["mock_record_usage"].execute.call_args
    assert call_args.kwargs.get("request_type") == cat


@then(parsers.parse("該 call 的 cache_read_tokens 應為 {n:d}"))
def verify_record_usage_cache_read(context, n):
    call_args = context["mock_record_usage"].execute.call_args
    usage = call_args.kwargs.get("usage")
    assert usage is not None
    assert usage.cache_read_tokens == n


@then(parsers.parse("該 call 的 input_tokens 應為 {n:d}"))
def verify_record_usage_input_tokens(context, n):
    call_args = context["mock_record_usage"].execute.call_args
    usage = call_args.kwargs.get("usage")
    assert usage is not None
    assert usage.input_tokens == n


@then(parsers.parse('該 call 的 tenant_id 應為 "{tid}"'))
def verify_record_usage_tenant_id(context, tid):
    call_args = context["mock_record_usage"].execute.call_args
    assert call_args.kwargs.get("tenant_id") == tid


# ════════════════════════════════════════════════════════════════
# Scenario 3: ClassifyKbUseCase
# ════════════════════════════════════════════════════════════════


@given(parsers.parse(
    "ClassifyKbUseCase 配置好 mock cluster service 已累計 input={inp:d} output={out:d}"
))
def setup_classify_kb(context, inp, out):
    mock_cluster = AsyncMock()
    mock_cluster.last_input_tokens = inp
    mock_cluster.last_output_tokens = out
    mock_cluster.last_model = "anthropic:claude-sonnet-4-6-20260415"
    mock_cluster.classify = AsyncMock(return_value=(
        [SimpleNamespace(id="cat-1")],  # categories
        {"chunk-1": "cat-1"},  # chunk_to_cat
    ))
    context["mock_cluster"] = mock_cluster


@given("注入 mock RecordUsageUseCase")
def setup_classify_kb_record(context):
    mock_record = AsyncMock()
    mock_record.execute = AsyncMock()
    context["mock_record_usage"] = mock_record


@when(parsers.parse(
    '呼叫 ClassifyKbUseCase.execute kb_id="{kb_id}" tenant_id="{tid}"'
))
def call_classify_kb(context, kb_id, tid):
    mock_kb_repo = AsyncMock()
    mock_kb_repo.find_by_id = AsyncMock(return_value=SimpleNamespace(
        classification_model="anthropic:claude-sonnet-4-6-20260415",
    ))
    mock_doc_repo = AsyncMock()
    mock_doc_repo.find_chunk_ids_by_kb = AsyncMock(
        return_value={"d-1": ["chunk-1"]}
    )
    mock_cat_repo = AsyncMock()
    mock_cat_repo.delete_by_kb = AsyncMock()
    mock_cat_repo.save_batch = AsyncMock()
    mock_cat_repo.update_chunk_counts = AsyncMock()
    mock_vector_store = AsyncMock()
    mock_vector_store.fetch_vectors = AsyncMock(return_value=[
        ("chunk-1", [0.1] * 3072, {"content": "test"}),
    ])

    use_case = ClassifyKbUseCase(
        knowledge_base_repository=mock_kb_repo,
        document_repository=mock_doc_repo,
        category_repository=mock_cat_repo,
        vector_store=mock_vector_store,
        classification_service=context["mock_cluster"],
        record_usage=context["mock_record_usage"],
    )

    # 跳過實際 SQL session 操作（chunks->category 對應），只驗證 record_usage
    with patch(
        "src.infrastructure.db.engine.async_session_factory",
        side_effect=Exception("skip session - test only verifies record_usage"),
    ):
        try:
            _run(use_case.execute(kb_id=kb_id, tenant_id=tid))
        except Exception:
            pass  # 預期會在 session 階段中斷，但 record_usage 已先執行


# ════════════════════════════════════════════════════════════════
# Scenario 4: IntentClassifier
# ════════════════════════════════════════════════════════════════


@given(parsers.parse(
    "IntentClassifier 配置好 mock LLMService 回傳 input={inp:d} output={out:d}"
))
def setup_intent_classifier(context, inp, out):
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=LLMResult(
        text="worker_a",
        usage=TokenUsage(
            model="test-model",
            input_tokens=inp,
            output_tokens=out,
            total_tokens=inp + out,
        ),
    ))
    context["mock_llm"] = mock_llm


@when(parsers.parse("呼叫 classify_workers 帶 {n:d} 個 worker"))
def call_classify_workers(context, n):
    classifier = IntentClassifier(
        llm_service=context["mock_llm"],
        record_usage=context["mock_record_usage"],
    )
    workers = [
        SimpleNamespace(name=f"worker_{chr(97 + i)}", description=f"desc {i}")
        for i in range(n)
    ]
    _run(classifier.classify_workers(
        user_message="test message",
        router_context="",
        workers=workers,
        tenant_id=context["tenant_id"],
    ))


# ════════════════════════════════════════════════════════════════
# Scenario 5: UsageCategory enum coverage
# ════════════════════════════════════════════════════════════════


@given("UsageCategory enum 已定義")
def setup_usage_category(context):
    context["enum"] = UsageCategory


@when("列出所有 enum 值")
def list_enum_values(context):
    context["enum_values"] = {e.value for e in context["enum"]}


@then(parsers.parse(
    '應至少包含 "{a}" "{b}" "{c}" "{d}" "{e}" "{f}" "{g}"'
))
def verify_enum_contains(context, a, b, c, d, e, f, g):
    required = {a, b, c, d, e, f, g}
    assert required.issubset(context["enum_values"])
