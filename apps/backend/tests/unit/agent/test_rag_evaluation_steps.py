"""BDD steps for RAG Evaluation use case."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.observability.rag_evaluation_use_case import RAGEvaluationUseCase
from src.domain.observability.evaluation import EvalDimension, EvalResult
from src.domain.observability.trace_record import RAGTraceRecord

scenarios("unit/agent/rag_evaluation.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


# ── Given ──

@given("一個 RAG 評估用例使用 mock LLM")
def setup_mock_llm(context):
    context["llm_service"] = AsyncMock()
    context["use_case"] = RAGEvaluationUseCase(
        llm_service=context["llm_service"]
    )


@given(
    parsers.parse("LLM 回傳評分 context_precision {cp} 和 context_recall {cr}"),
)
def mock_l1_scores(context, cp, cr):
    resp = MagicMock()
    resp.text = json.dumps({
        "context_precision": float(cp),
        "context_recall": float(cr),
        "explanation": "測試用評分",
    })
    context["llm_service"].generate.return_value = resp


@given(
    parsers.parse("LLM 回傳評分 faithfulness {f} 和 relevancy {r}"),
)
def mock_l2_scores(context, f, r):
    resp = MagicMock()
    resp.text = json.dumps({
        "faithfulness": float(f),
        "relevancy": float(r),
        "explanation": "測試用評分",
    })
    context["llm_service"].generate.return_value = resp


@given(
    parsers.parse("LLM 回傳評分 agent_efficiency {ae} 和 tool_selection {ts}"),
)
def mock_l3_scores(context, ae, ts):
    resp = MagicMock()
    resp.text = json.dumps({
        "agent_efficiency": float(ae),
        "tool_selection": float(ts),
        "explanation": "測試用評分",
    })
    context["llm_service"].generate.return_value = resp


@given("一個包含多維度的 EvalResult")
def setup_eval_result(context):
    context["eval_result"] = EvalResult(
        layer="L1",
        dimensions=[
            EvalDimension(name="context_precision", score=0.8),
            EvalDimension(name="context_recall", score=0.6),
        ],
    )


# ── When ──

@when(
    parsers.parse('執行 L1 評估查詢 "{query}" 和 chunks ["{chunk}"]'),
    target_fixture="result",
)
def run_l1_eval(context, query, chunk):
    return _run(
        context["use_case"].evaluate_l1(
            query=query,
            chunks=[chunk],
            tenant_id="t-1",
        )
    )


@when(
    parsers.parse('執行 L2 評估查詢 "{query}" 回答 "{answer}" 上下文 "{ctx}"'),
    target_fixture="result",
)
def run_l2_eval(context, query, answer, ctx):
    return _run(
        context["use_case"].evaluate_l2(
            query=query,
            answer=answer,
            all_context=ctx,
            tenant_id="t-1",
        )
    )


@when(
    parsers.parse('執行 L3 評估查詢 "{query}" 和工具呼叫記錄'),
    target_fixture="result",
)
def run_l3_eval(context, query):
    trace = RAGTraceRecord(query=query, tenant_id="t-1")
    tool_calls = [
        {"tool_name": "rag_query", "tool_input": "退貨政策"},
    ]
    return _run(
        context["use_case"].evaluate_l3(
            query=query,
            trace_records=[trace],
            tool_calls=tool_calls,
            tenant_id="t-1",
        )
    )


# ── Then ──

@then(parsers.parse('評估結果的 layer 應為 "{expected}"'))
def check_layer(result, expected):
    assert result.layer == expected


@then(parsers.parse("應包含 {dim_name} 維度分數 {expected_score}"))
def check_dimension_score(result, dim_name, expected_score):
    found = [d for d in result.dimensions if d.name == dim_name]
    assert len(found) == 1, f"維度 {dim_name} 未找到，現有: {[d.name for d in result.dimensions]}"
    assert found[0].score == pytest.approx(float(expected_score), abs=0.01)


@then("avg_score 應為各維度分數的平均值")
def check_avg_score(context):
    er = context["eval_result"]
    expected = (0.8 + 0.6) / 2
    assert er.avg_score == pytest.approx(expected, abs=0.001)
