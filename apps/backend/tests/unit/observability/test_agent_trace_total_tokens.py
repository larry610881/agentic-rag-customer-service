"""Unit test — AgentExecutionTrace.finish() token aggregation (Sprint A+ Bug 2)"""

from __future__ import annotations

from src.domain.observability.agent_trace import AgentExecutionTrace


def _make_trace() -> AgentExecutionTrace:
    return AgentExecutionTrace(
        trace_id="trace-1",
        tenant_id="t1",
        agent_mode="react",
        source="web",
        llm_model="claude-haiku-4-5",
        llm_provider="anthropic",
    )


def test_finish_aggregates_token_usage_from_nodes():
    trace = _make_trace()
    trace.add_node(
        node_type="agent_llm",
        label="llm-1",
        parent_id=None,
        start_ms=0,
        end_ms=100,
        token_usage={
            "input_tokens": 1000,
            "output_tokens": 200,
            "estimated_cost": 0.005,
        },
    )
    trace.add_node(
        node_type="agent_llm",
        label="llm-2",
        parent_id=None,
        start_ms=100,
        end_ms=250,
        token_usage={
            "input_tokens": 10000,
            "output_tokens": 300,
            "estimated_cost": 0.015,
        },
    )

    trace.finish(total_ms=250.0)

    assert trace.total_tokens is not None
    assert trace.total_tokens["input_tokens"] == 11000
    assert trace.total_tokens["output_tokens"] == 500
    assert trace.total_tokens["total"] == 11500
    assert abs(trace.total_tokens["estimated_cost"] - 0.020) < 1e-6


def test_finish_skips_nodes_without_token_usage():
    trace = _make_trace()
    trace.add_node(
        node_type="tool_call",
        label="search",
        parent_id=None,
        start_ms=0,
        end_ms=50,
        token_usage=None,  # tool call 沒 token
    )
    trace.add_node(
        node_type="agent_llm",
        label="llm",
        parent_id=None,
        start_ms=50,
        end_ms=150,
        token_usage={"input_tokens": 500, "output_tokens": 100, "estimated_cost": 0.002},
    )

    trace.finish(total_ms=150.0)

    assert trace.total_tokens == {
        "input_tokens": 500,
        "output_tokens": 100,
        "total": 600,
        "estimated_cost": 0.002,
    }


def test_finish_with_no_llm_nodes_leaves_total_tokens_none():
    trace = _make_trace()
    trace.add_node(
        node_type="user_input",
        label="user",
        parent_id=None,
        start_ms=0,
        end_ms=5,
        token_usage=None,
    )
    trace.finish(total_ms=5.0)
    # 無任何 LLM token → 保持 None（避免顯示假的 0/0 值）
    assert trace.total_tokens is None


def test_finish_handles_missing_keys_in_token_usage():
    trace = _make_trace()
    trace.add_node(
        node_type="agent_llm",
        label="llm",
        parent_id=None,
        start_ms=0,
        end_ms=100,
        token_usage={"input_tokens": 800},  # 缺 output / cost
    )
    trace.finish(total_ms=100.0)

    assert trace.total_tokens == {
        "input_tokens": 800,
        "output_tokens": 0,
        "total": 800,
        "estimated_cost": 0,
    }
