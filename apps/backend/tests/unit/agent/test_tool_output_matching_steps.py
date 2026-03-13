"""BDD steps for tool output matching."""

from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.langgraph.react_agent_service import _backfill_tool_output

scenarios("unit/agent/tool_output_matching.feature")


@pytest.fixture()
def context():
    return {}


# ── Given ──


@given("有兩次 rag_query 工具呼叫記錄帶有不同 tool_call_id")
def two_tool_calls_with_ids(context):
    context["tool_calls"] = [
        {"tool_name": "rag_query", "tool_call_id": "tc-001", "reasoning": ""},
        {"tool_name": "rag_query", "tool_call_id": "tc-002", "reasoning": ""},
    ]


@given("有兩次 rag_query 工具呼叫記錄無 tool_call_id")
def two_tool_calls_no_ids(context):
    context["tool_calls"] = [
        {
            "tool_name": "rag_query",
            "tool_call_id": "",
            "reasoning": "",
            "tool_output": "first output",
        },
        {"tool_name": "rag_query", "tool_call_id": "", "reasoning": ""},
    ]


# ── When ──


@when("第一個 ToolMessage 帶有第一個 tool_call_id 回傳")
def backfill_first(context):
    msg = SimpleNamespace(
        name="rag_query", tool_call_id="tc-001", content="result-1"
    )
    _backfill_tool_output(context["tool_calls"], msg, "result-1")


@when("一個 rag_query ToolMessage 回傳")
def backfill_by_name(context):
    msg = SimpleNamespace(
        name="rag_query", tool_call_id="", content="result-fallback"
    )
    _backfill_tool_output(context["tool_calls"], msg, "result-fallback")


@when("兩個 ToolMessage 依序回傳帶有各自的 tool_call_id")
def backfill_both(context):
    msg1 = SimpleNamespace(
        name="rag_query", tool_call_id="tc-001", content="result-1"
    )
    msg2 = SimpleNamespace(
        name="rag_query", tool_call_id="tc-002", content="result-2"
    )
    _backfill_tool_output(context["tool_calls"], msg1, "result-1")
    _backfill_tool_output(context["tool_calls"], msg2, "result-2")


# ── Then ──


@then("第一個 tool_call 應有 tool_output")
def first_has_output(context):
    assert context["tool_calls"][0].get("tool_output") == "result-1"


@then("第二個 tool_call 不應有 tool_output")
def second_no_output(context):
    assert "tool_output" not in context["tool_calls"][1]


@then("最後一個無 output 的 rag_query 應被填充")
def last_empty_filled(context):
    assert context["tool_calls"][1].get("tool_output") == "result-fallback"


@then("兩個 tool_call 應各自有正確的 tool_output")
def both_have_correct_output(context):
    assert context["tool_calls"][0]["tool_output"] == "result-1"
    assert context["tool_calls"][1]["tool_output"] == "result-2"
