"""Trace tool payload 完整記錄 BDD Step Definitions"""

import json

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.observability.agent_trace import ExecutionNode
from src.infrastructure.observability.tool_trace_recorder import (
    record_tool_output,
)

scenarios("unit/observability/trace_tool_payload.feature")


@pytest.fixture
def context():
    return {}


def _make_node() -> ExecutionNode:
    return ExecutionNode(
        node_type="tool_call",
        label="rag_query",
        parent_id=None,
        start_ms=0.0,
        end_ms=10.0,
        duration_ms=10.0,
        token_usage=None,
        metadata={},
    )


# ---------- Given ----------


@given("一個會回傳 JSON dict 的 tool node")
def given_json_tool_node(context):
    context["node"] = _make_node()
    context["tool_output_raw"] = {
        "success": True,
        "context": "查到退貨政策",
        "sources": [{"document_name": "policy.md", "score": 0.9}],
    }
    context["content_str"] = json.dumps(
        context["tool_output_raw"], ensure_ascii=False
    )


@given("一個回傳純文字結果的 tool node")
def given_plain_text_tool_node(context):
    context["node"] = _make_node()
    context["content_str"] = "純文字回覆，非 JSON"


@given("一個 transfer_to_human tool 回傳含 contact 的 payload")
def given_contact_tool_node(context):
    context["node"] = _make_node()
    context["node"].label = "transfer_to_human_agent"
    context["tool_output_raw"] = {
        "success": True,
        "context": "已準備真人客服聯絡方式",
        "contact": {
            "label": "聯絡真人客服",
            "url": "https://example.com/support",
            "type": "url",
        },
    }
    context["content_str"] = json.dumps(
        context["tool_output_raw"], ensure_ascii=False
    )


# ---------- When ----------


@when("ReactAgentService 記錄 tool trace")
def when_record_trace(context):
    record_tool_output(context["node"], context["content_str"])


@when("ReactAgentService 串流處理 tool 結果")
def when_stream_record(context):
    record_tool_output(context["node"], context["content_str"])


# ---------- Then ----------


@then("對應 ExecutionNode 的 metadata 應包含完整 tool_output dict")
def then_metadata_has_tool_output(context):
    md = context["node"].metadata
    assert "tool_output" in md
    assert md["tool_output"] == context["tool_output_raw"]


@then("對應 ExecutionNode 的 metadata 不應包含 tool_output 欄位")
def then_metadata_no_tool_output(context):
    md = context["node"].metadata
    assert "tool_output" not in md


@then("對應 ExecutionNode 的 metadata 應包含 contact 欄位")
def then_metadata_has_contact(context):
    md = context["node"].metadata
    assert "contact" in md
    assert md["contact"]["label"] == "聯絡真人客服"
    assert md["contact"]["url"] == "https://example.com/support"
