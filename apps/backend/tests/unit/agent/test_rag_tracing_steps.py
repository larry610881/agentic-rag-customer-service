"""BDD steps for RAG Tracing."""
import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.observability.trace_record import RAGTraceRecord
from src.infrastructure.observability.rag_tracer import RAGTracer

scenarios("unit/agent/rag_tracing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def context():
    return {}


# ---------- Given ----------


@given("一個含有 system prompt 的追蹤記錄")
def create_trace_with_prompt(context):
    context["prompt"] = "你是一個專業的客服助理"
    context["trace"] = RAGTraceRecord(
        query="退貨政策",
        tenant_id="T001",
        prompt_snapshot=context["prompt"],
    )


@given("一個 RAG 追蹤器已初始化")
def init_tracer(context):
    RAGTracer.init()
    context["tracer"] = RAGTracer


@given("已完成 2 筆追蹤記錄")
def create_two_traces(context):
    tracer = context["tracer"]

    trace1 = tracer.start_trace("問題一", "T001")
    trace1.add_step("retrieve", 50.0, chunk_count=2)
    trace1.chunk_count = 2
    trace1.finish(50.0)

    trace2 = tracer.start_trace("問題二", "T001")
    trace2.add_step("retrieve", 60.0, chunk_count=1)
    trace2.chunk_count = 1
    trace2.finish(60.0)


# ---------- When ----------


@when("序列化為 dict")
def serialize_trace(context):
    context["trace_dict"] = context["trace"].to_dict()


@when(parsers.parse('開始一次 RAG 查詢追蹤 "{query}" 租戶 "{tenant_id}"'))
def start_trace(context, query, tenant_id):
    tracer = context["tracer"]
    trace = tracer.start_trace(query, tenant_id)
    context["trace"] = trace


@when(parsers.parse("記錄 embed 步驟耗時 {ms:d}ms"))
def record_embed_step(context, ms):
    context["trace"].add_step("embed", float(ms))


@when(parsers.parse("記錄 retrieve 步驟耗時 {ms:d}ms 取得 {count:d} 個 chunks"))
def record_retrieve_step(context, ms, count):
    context["trace"].add_step("retrieve", float(ms), chunk_count=count)
    context["trace"].chunk_count = count


@when(parsers.parse("完成追蹤總耗時 {ms:d}ms"))
def finish_trace(context, ms):
    context["trace"].finish(float(ms))


@when("執行 flush")
def do_flush(context):
    context["flush_result"] = RAGTracer.flush()


# ---------- Then ----------


@then("應包含 prompt_snapshot 欄位且值為該 system prompt")
def check_prompt_snapshot(context):
    d = context["trace_dict"]
    assert "prompt_snapshot" in d
    assert d["prompt_snapshot"] == context["prompt"]


@then(parsers.parse("追蹤記錄應包含 {count:d} 個步驟"))
def check_step_count(context, count):
    assert len(context["trace"].steps) == count


@then(parsers.parse("追蹤記錄總耗時應為 {ms:d}ms"))
def check_total_ms(context, ms):
    assert context["trace"].total_ms == float(ms)


@then(parsers.parse("追蹤記錄 chunk_count 應為 {count:d}"))
def check_chunk_count(context, count):
    assert context["trace"].chunk_count == count


@then(parsers.parse("應回傳 {count:d} 筆追蹤記錄"))
def check_flush_count(context, count):
    assert len(context["flush_result"]) == count


@then("追蹤 buffer 應為空")
def check_buffer_empty(context):
    # After flush, another flush should return empty
    second_flush = RAGTracer.flush()
    assert len(second_flush) == 0
