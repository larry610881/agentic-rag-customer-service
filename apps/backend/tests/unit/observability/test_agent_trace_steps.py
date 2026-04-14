"""BDD steps for Agent Execution Trace — Collector + Domain VO."""
import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.observability.agent_trace import (
    AgentExecutionTrace,
    ExecutionNode,
)
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

scenarios("unit/observability/agent_trace.feature")


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


@given(parsers.parse(
    '一個 Agent 追蹤收集器已啟動 模式 "{mode}" 租戶 "{tenant_id}"'
))
def start_collector(context, mode, tenant_id):
    trace = AgentTraceCollector.start(tenant_id, mode)
    context["trace"] = trace
    context["node_ids"] = {}


@given("一個包含 metadata 的 ExecutionNode")
def create_node_with_metadata(context):
    context["node"] = ExecutionNode(
        node_type="tool_call",
        label="rag_query",
        parent_id="parent-123",
        start_ms=10.0,
        end_ms=50.0,
        duration_ms=40.0,
        token_usage={"input_tokens": 100, "output_tokens": 50},
        metadata={"tool_name": "rag_query", "result_length": 500},
    )


# ---------- When ----------


@when(parsers.parse("新增 user_input 節點 起始 {start:d}ms 結束 {end:d}ms"))
def add_user_input(context, start, end):
    node_id = AgentTraceCollector.add_node(
        "user_input", "使用者輸入", None,
        float(start), float(end),
        message_preview="測試訊息",
    )
    context["node_ids"]["user_input"] = node_id


@when(parsers.parse(
    "新增 agent_llm 節點 起始 {start:d}ms 結束 {end:d}ms 含 token 用量"
))
def add_agent_llm(context, start, end):
    node_id = AgentTraceCollector.add_node(
        "agent_llm", "ReAct 迭代 1", None,
        float(start), float(end),
        token_usage={"input_tokens": 200, "output_tokens": 80},
        iteration=1,
        decision="tool_call",
    )
    context["node_ids"]["agent_llm"] = node_id


@when(parsers.parse(
    '新增 tool_call 節點 "{tool}" 起始 {start:d}ms 結束 {end:d}ms'
    ' 掛在上一個 agent_llm 下'
))
def add_tool_call(context, tool, start, end):
    parent_id = context["node_ids"]["agent_llm"]
    node_id = AgentTraceCollector.add_node(
        "tool_call", tool, parent_id,
        float(start), float(end),
        tool_name=tool,
    )
    context["node_ids"]["tool_call"] = node_id


@when(parsers.parse(
    "新增 final_response 節點 起始 {start:d}ms 結束 {end:d}ms"
))
def add_final_response(context, start, end):
    node_id = AgentTraceCollector.add_node(
        "final_response", "最終回覆", None,
        float(start), float(end),
    )
    context["node_ids"]["final_response"] = node_id


@when(parsers.parse(
    '新增 supervisor_dispatch 節點 "{worker}" 起始 {start:d}ms 結束 {end:d}ms'
))
def add_supervisor_dispatch(context, worker, start, end):
    node_id = AgentTraceCollector.add_node(
        "supervisor_dispatch", f"選擇 {worker}", None,
        float(start), float(end),
        selected_worker=worker,
    )
    context["node_ids"]["supervisor_dispatch"] = node_id


@when(parsers.parse(
    '新增 worker_execution 節點 "{worker}" 起始 {start:d}ms 結束 {end:d}ms'
))
def add_worker_execution(context, worker, start, end):
    node_id = AgentTraceCollector.add_node(
        "worker_execution", worker, None,
        float(start), float(end),
    )
    context["node_ids"]["worker_execution"] = node_id


@when(parsers.parse("完成追蹤總耗時 {ms:d}ms"))
def finish_trace(context, ms):
    context["finished_trace"] = AgentTraceCollector.finish(float(ms))


@when("在未啟動的收集器上新增節點")
def add_node_without_start(context):
    # Ensure no active trace
    AgentTraceCollector.finish(0)
    context["result_id"] = AgentTraceCollector.add_node(
        "user_input", "test", None, 0, 0,
    )


@when("序列化為 dict")
def serialize_node(context):
    context["node_dict"] = context["node"].to_dict()


# ---------- Then ----------


@then(parsers.parse("追蹤記錄應包含 {count:d} 個節點"))
def check_node_count(context, count):
    trace = context.get("finished_trace") or context["trace"]
    assert len(trace.nodes) == count


@then(parsers.parse('追蹤記錄模式應為 "{mode}"'))
def check_agent_mode(context, mode):
    trace = context.get("finished_trace") or context["trace"]
    assert trace.agent_mode == mode


@then(parsers.parse("追蹤記錄總耗時應為 {ms:d}ms"))
def check_total_ms(context, ms):
    trace = context["finished_trace"]
    assert trace.total_ms == float(ms)


@then("tool_call 節點的 parent 應為 agent_llm 節點")
def check_parent_id(context):
    trace = context["finished_trace"]
    tool_node = next(
        n for n in trace.nodes if n.node_type == "tool_call"
    )
    agent_node_id = context["node_ids"]["agent_llm"]
    assert tool_node.parent_id == agent_node_id


@then("應回傳追蹤記錄且 ContextVar 已清空")
def check_finish_clears_contextvar(context):
    trace = context["finished_trace"]
    assert trace is not None
    assert trace.total_ms == 100.0
    # ContextVar should be cleared
    assert AgentTraceCollector.current() is None


@then("應回傳空字串且不報錯")
def check_empty_node_id(context):
    assert context["result_id"] == ""


@then("應包含所有欄位且 metadata 正確")
def check_node_dict(context):
    d = context["node_dict"]
    assert d["node_type"] == "tool_call"
    assert d["label"] == "rag_query"
    assert d["parent_id"] == "parent-123"
    assert d["start_ms"] == 10.0
    assert d["end_ms"] == 50.0
    assert d["duration_ms"] == 40.0
    assert d["token_usage"]["input_tokens"] == 100
    assert d["metadata"]["tool_name"] == "rag_query"
    assert d["metadata"]["result_length"] == 500
