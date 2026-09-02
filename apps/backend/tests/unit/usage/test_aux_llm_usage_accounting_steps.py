"""輔助 LLM 呼叫記帳 BDD Step Definitions（Issue #59）"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.memory.extract_memory_use_case import (
    ExtractMemoryCommand,
    ExtractMemoryUseCase,
)
from src.application.rag._hyde_generator import generate_hyde
from src.application.rag._query_rewriter import rewrite_query
from src.domain.conversation.entity import Message
from src.domain.conversation.history_strategy import HistoryStrategyConfig
from src.domain.conversation.value_objects import MessageId
from src.domain.memory.services import ExtractedFact
from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.infrastructure.conversation.summary_recent_strategy import (
    SummaryRecentStrategy,
)
from src.infrastructure.llm.llm_caller import LLMCallResult
from src.infrastructure.memory.llm_memory_extraction_service import (
    LLMMemoryExtractionService,
)
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

scenarios("unit/usage/aux_llm_usage_accounting.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    trace = AgentTraceCollector.start(tenant_id="tenant-001", agent_mode="react")
    yield {"trace": trace, "record_usage": None}
    AgentTraceCollector.finish(0.0)


# ── rewrite / HyDE ──


@given(parsers.parse(
    'call_llm 回傳文字 "{text}" 且 input {inp:d} output {out:d} tokens'
))
def call_llm_returns(context, text, inp, out):
    context["llm_result"] = LLMCallResult(
        text=text, input_tokens=inp, output_tokens=out, model="claude-haiku-4-5",
    )


@given("已注入 record_usage")
def inject_record_usage(context):
    context["record_usage"] = AsyncMock()


@when(parsers.parse('以 tenant "{tenant_id}" 執行 rewrite_query'))
def run_rewrite(context, tenant_id):
    with patch(
        "src.infrastructure.llm.llm_caller.call_llm",
        AsyncMock(return_value=context["llm_result"]),
    ):
        context["result"] = _run(rewrite_query(
            "原始問題",
            api_key_resolver=AsyncMock(return_value="key"),
            record_usage=context["record_usage"],
            tenant_id=tenant_id,
        ))


@when(parsers.parse('以 tenant "{tenant_id}" 執行 generate_hyde'))
def run_hyde(context, tenant_id):
    with patch(
        "src.infrastructure.llm.llm_caller.call_llm",
        AsyncMock(return_value=context["llm_result"]),
    ):
        context["result"] = _run(generate_hyde(
            "原始問題",
            api_key_resolver=AsyncMock(return_value="key"),
            record_usage=context["record_usage"],
            tenant_id=tenant_id,
        ))


@then(parsers.parse(
    '應以 request_type "{category}" 記錄 tenant "{tenant_id}" 的用量 '
    "input {inp:d} output {out:d}"
))
def usage_recorded(context, category, tenant_id, inp, out):
    context["record_usage"].execute.assert_awaited_once()
    kwargs = context["record_usage"].execute.call_args.kwargs
    assert kwargs["tenant_id"] == tenant_id
    assert kwargs["request_type"] == category
    assert kwargs["usage"].input_tokens == inp
    assert kwargs["usage"].output_tokens == out


@then(parsers.parse('應新增 label 為 "{label}" 的 trace 節點'))
def trace_node_added(context, label):
    labels = [n.label for n in context["trace"].nodes]
    assert label in labels, labels


@then(parsers.parse('rewrite 結果應為 "{text}"'))
def rewrite_result(context, text):
    assert context["result"] == text


# ── memory extraction (infrastructure) ──


@given(parsers.parse(
    "LLMService.generate 回傳 JSON 事實陣列且 input {inp:d} output {out:d} tokens"
))
def llm_generate_returns(context, inp, out):
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value=LLMResult(
        text='[{"category":"preference","key":"color","value":"blue","confidence":0.9}]',
        usage=TokenUsage(model="m", input_tokens=inp, output_tokens=out),
    ))
    context["llm"] = llm


@when("執行記憶萃取並帶 usage_collector")
def run_extraction(context):
    service = LLMMemoryExtractionService(llm_service=context["llm"])
    context["collector"] = {}
    context["facts"] = _run(service.extract_facts(
        conversation_messages=[{"role": "user", "content": "我喜歡藍色"}],
        existing_facts=[],
        usage_collector=context["collector"],
    ))


@then("應以 system_prompt 與 user_message 關鍵字參數呼叫 generate")
def generate_called_correctly(context):
    kwargs = context["llm"].generate.call_args.kwargs
    assert "system_prompt" in kwargs and "user_message" in kwargs
    assert "prompt" not in kwargs


@then(parsers.parse("萃取結果應含 {n:d} 筆事實"))
def facts_count(context, n):
    assert len(context["facts"]) == n


@then(parsers.parse("usage_collector 應含 input {inp:d} output {out:d}"))
def collector_has_usage(context, inp, out):
    usage = context["collector"]["usage"]
    assert usage.input_tokens == inp and usage.output_tokens == out


# ── memory extraction (use case) ──


@given(parsers.parse(
    "萃取服務回傳 {n:d} 筆事實並回填 usage input {inp:d} output {out:d}"
))
def extraction_service_with_usage(context, n, inp, out):
    async def _extract(conversation_messages, existing_facts,
                       extraction_prompt="", usage_collector=None):
        if usage_collector is not None:
            usage_collector["usage"] = TokenUsage(
                model="m", input_tokens=inp, output_tokens=out
            )
        return [ExtractedFact(category="c", key=f"k{i}", value="v") for i in range(n)]

    service = AsyncMock()
    service.extract_facts = AsyncMock(side_effect=_extract)
    context["extraction_service"] = service


@given("記憶萃取用例已注入 record_usage")
def use_case_with_record_usage(context):
    context["record_usage"] = AsyncMock()


@when(parsers.parse('以 tenant "{tenant_id}" 執行記憶萃取用例'))
def run_extract_use_case(context, tenant_id):
    repo = AsyncMock()
    repo.find_by_profile = AsyncMock(return_value=[])
    repo.upsert_by_key = AsyncMock()
    uc = ExtractMemoryUseCase(
        memory_fact_repository=repo,
        extraction_service=context["extraction_service"],
        record_usage=context["record_usage"],
    )
    _run(uc.execute(ExtractMemoryCommand(
        profile_id="p1", tenant_id=tenant_id, conversation_id="c1",
        messages=[{"role": "user", "content": "hi"}],
    )))


# ── summary_recent ──


@given(parsers.parse(
    "summary_recent 策略已注入 record_usage 且 LLM 回傳摘要 "
    "input {inp:d} output {out:d}"
))
def summary_strategy(context, inp, out):
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value=LLMResult(
        text="摘要", usage=TokenUsage(model="m", input_tokens=inp, output_tokens=out),
    ))
    context["record_usage"] = AsyncMock()
    context["strategy"] = SummaryRecentStrategy(
        llm_service=llm, record_usage=context["record_usage"],
    )


@when(parsers.parse('以 tenant "{tenant_id}" 對 {n:d} 則訊息執行 summary_recent'))
def run_summary(context, tenant_id, n):
    messages = [
        Message(
            id=MessageId(value=f"m{i}"), conversation_id="c1",
            role="user" if i % 2 == 0 else "assistant", content=f"訊息 {i}",
            created_at=datetime.now(timezone.utc),
        )
        for i in range(n)
    ]
    _run(context["strategy"].process(
        messages, HistoryStrategyConfig(recent_turns=1, tenant_id=tenant_id),
    ))
