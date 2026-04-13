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
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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


@given(
    parsers.parse("LLM 回傳合併評分 context_precision {cp} 和 faithfulness {f}"),
)
def mock_combined_l1_l2_scores(context, cp, f):
    resp = MagicMock()
    resp.text = json.dumps({
        "context_precision": float(cp),
        "context_recall": 0.7,
        "faithfulness": float(f),
        "relevancy": 0.85,
        "explanation": "合併測試評分",
    })
    context["llm_service"].generate.return_value = resp


@given(
    parsers.parse("LLM 回傳合併評分 faithfulness {f} 和 relevancy {r}"),
)
def mock_combined_l2_only_scores(context, f, r):
    resp = MagicMock()
    resp.text = json.dumps({
        "faithfulness": float(f),
        "relevancy": float(r),
        "explanation": "合併測試評分",
    })
    context["llm_service"].generate.return_value = resp


@given("一個 RAG 評估用例使用帶有 model_name 的 mock LLM")
def setup_mock_llm_with_model_name(context):
    llm = AsyncMock()
    llm.model_name = "gemini-2.5-flash-lite"
    resp = MagicMock()
    resp.text = json.dumps({
        "faithfulness": 0.9,
        "relevancy": 0.85,
        "explanation": "model name test",
    })
    llm.generate.return_value = resp
    context["llm_service"] = llm
    context["use_case"] = RAGEvaluationUseCase(llm_service=llm)


@given("LLM 回傳含 chunk_scores 的 L1 評估結果")
def mock_l1_with_chunk_scores(context):
    resp = MagicMock()
    resp.text = json.dumps({
        "context_precision": 0.85,
        "context_recall": 0.7,
        "chunk_scores": [
            {"index": 0, "score": 0.9, "reason": "高度相關"},
            {"index": 1, "score": 0.8, "reason": "部分相關"},
            {"index": 2, "score": 0.3, "reason": "不太相關"},
        ],
        "explanation": "逐 chunk 評分測試",
    })
    context["llm_service"].generate.return_value = resp


@given("LLM 回傳含 chunk_scores 的合併評估結果")
def mock_combined_with_chunk_scores(context):
    resp = MagicMock()
    resp.text = json.dumps({
        "context_precision": 0.8,
        "context_recall": 0.7,
        "faithfulness": 0.9,
        "relevancy": 0.85,
        "chunk_scores": [
            {"index": 0, "score": 0.95, "reason": "完全相關"},
        ],
        "explanation": "合併 chunk_scores 測試",
    })
    context["llm_service"].generate.return_value = resp


@when(
    parsers.parse('執行 L1 評估查詢 "{query}" 和 {n:d} 個 chunks'),
    target_fixture="result",
)
def run_l1_eval_multi_chunks(context, query, n):
    chunks = [f"chunk content {i}" for i in range(n)]
    return _run(
        context["use_case"].evaluate_l1(
            query=query,
            chunks=chunks,
            tenant_id="t-1",
        )
    )


@when("執行合併評估且 L1 啟用", target_fixture="result")
def run_combined_with_l1(context):
    return _run(
        context["use_case"].evaluate_combined(
            query="退貨政策",
            answer="30天內可退貨",
            all_context="退貨政策原文",
            chunks=["退貨政策原文"],
            tool_calls=[],
            run_l1=True,
            run_l2=True,
            has_rag_sources=True,
            tenant_id="t-1",
        )
    )


@then("context_precision 維度應包含 chunk_scores metadata")
def check_chunk_scores_metadata(result):
    cp = [d for d in result.dimensions if d.name == "context_precision"]
    assert len(cp) == 1
    assert cp[0].metadata is not None
    assert "chunk_scores" in cp[0].metadata


@then(parsers.parse("chunk_scores 應有 {n:d} 筆且每筆含 index score reason"))
def check_chunk_scores_structure(result, n):
    cp = [d for d in result.dimensions if d.name == "context_precision"][0]
    scores = cp.metadata["chunk_scores"]
    assert len(scores) == n
    for item in scores:
        assert "index" in item
        assert "score" in item
        assert "reason" in item


@then("context_precision 維度的 metadata 應包含 chunk_scores")
def check_combined_chunk_scores(result):
    cp = [d for d in result.dimensions if d.name == "context_precision"]
    assert len(cp) == 1
    assert cp[0].metadata is not None
    assert "chunk_scores" in cp[0].metadata
    assert len(cp[0].metadata["chunk_scores"]) >= 1


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


@when(
    parsers.parse('執行合併評估 L1+L2 查詢 "{query}" 有 RAG sources'),
    target_fixture="result",
)
def run_combined_with_rag(context, query):
    return _run(
        context["use_case"].evaluate_combined(
            query=query,
            answer="30天內可退貨",
            all_context="退貨政策原文",
            chunks=["退貨政策原文"],
            tool_calls=[],
            run_l1=True,
            run_l2=True,
            has_rag_sources=True,
            tenant_id="t-1",
        )
    )


@when(
    parsers.parse('執行合併評估 L1+L2 查詢 "{query}" 無 RAG sources'),
    target_fixture="result",
)
def run_combined_without_rag(context, query):
    return _run(
        context["use_case"].evaluate_combined(
            query=query,
            answer="這個商品500元",
            all_context="[query_products] 商品A 500元",
            chunks=["[query_products] 商品A 500元"],
            tool_calls=[{"tool_name": "query_products", "tool_input": "500元商品"}],
            run_l1=True,
            run_l2=True,
            has_rag_sources=False,
            tenant_id="t-1",
        )
    )


@when(
    parsers.parse('執行合併評估 L2 查詢 "{query}"'),
    target_fixture="result",
)
def run_combined_l2_only(context, query):
    return _run(
        context["use_case"].evaluate_combined(
            query=query,
            answer="30天內可退貨",
            all_context="退貨政策原文",
            chunks=["退貨政策原文"],
            tool_calls=[],
            run_l2=True,
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


@then("應只呼叫 LLM 一次")
def check_single_llm_call(context):
    assert context["llm_service"].generate.call_count == 1


@then("結果不應包含 context_precision 維度")
def check_no_context_precision(result):
    names = [d.name for d in result.dimensions]
    assert "context_precision" not in names
    assert "context_recall" not in names


@then(parsers.parse('評估結果的 model_used 應為 "{expected}"'))
def check_model_used(result, expected):
    assert result.model_used == expected


@then("avg_score 應為各維度分數的平均值")
def check_avg_score(context):
    er = context["eval_result"]
    expected = (0.8 + 0.6) / 2
    assert er.avg_score == pytest.approx(expected, abs=0.001)


# ── C9/C10: Pydantic validation scenarios ──


@given("LLM 回傳含百分比 chunk_scores 的評估結果")
def mock_percentage_chunk_scores(context):
    resp = MagicMock()
    resp.text = json.dumps({
        "context_precision": 0.8,
        "context_recall": 0.7,
        "chunk_scores": [
            {"index": 0, "score": "85%", "reason": "高度相關"},
            {"index": 1, "score": 70, "reason": "部分相關"},
        ],
        "explanation": "百分比測試",
    })
    context["llm_service"].generate.return_value = resp


@given("LLM 回傳無效 JSON")
def mock_malformed_json(context):
    resp = MagicMock()
    resp.text = "this is not valid json {{"
    context["llm_service"].generate.return_value = resp


@then("chunk_scores 的 score 應在 0-1 範圍內")
def check_normalized_scores(result):
    cp = [d for d in result.dimensions if d.name == "context_precision"]
    assert len(cp) == 1
    if cp[0].metadata and "chunk_scores" in cp[0].metadata:
        for cs in cp[0].metadata["chunk_scores"]:
            assert 0.0 <= cs["score"] <= 1.0, f"Score {cs['score']} out of range"


@then("評估結果的各維度分數應為 0.0")
def check_zero_scores(result):
    for dim in result.dimensions:
        assert dim.score == 0.0
