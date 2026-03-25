"""Prompt Optimizer Evaluator BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then, when

from prompt_optimizer.api_client import ChatResult
from prompt_optimizer.dataset import (
    Assertion,
    CostConfigData,
    Dataset,
    DatasetMetadata,
    TestCase,
)
from prompt_optimizer.evaluator import (
    PRIORITY_WEIGHTS,
    DatasetEvalSummary,
    Evaluator,
)

scenarios("unit/prompt_optimizer/evaluator.feature")


@pytest.fixture
def ctx():
    return {}


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_chat_result(
    answer: str = "這是正確的回答",
    usage: dict | None = None,
    tool_calls: list | None = None,
    sources: list | None = None,
    latency_ms: int = 100,
) -> ChatResult:
    return ChatResult(
        answer=answer,
        conversation_id="conv-test",
        tool_calls=tool_calls or [],
        sources=sources or [],
        usage=usage,
        latency_ms=latency_ms,
    )


def _make_dataset(
    test_cases: tuple[TestCase, ...],
    cost_config: CostConfigData | None = None,
) -> Dataset:
    return Dataset(
        metadata=DatasetMetadata(
            tenant_id="t-1",
            bot_id="b-1",
            cost_config=cost_config or CostConfigData(),
        ),
        test_cases=test_cases,
    )


# ═══════════════════════════════════════════════════════════════
# Scenario: 所有 assertions 通過
# ═══════════════════════════════════════════════════════════════


@given("一個包含 3 個 test cases 的 dataset")
def given_3_cases(ctx):
    cases = tuple(
        TestCase(
            id=f"tc-{i}",
            question=f"問題{i}",
            priority="P1",
            category="general",
            assertions=(
                Assertion(type="response_not_empty"),
                Assertion(type="contains_any", params={"keywords": ["回答"]}),
            ),
        )
        for i in range(1, 4)
    )
    ctx["dataset"] = _make_dataset(cases)


@given("所有 API 回應都正確")
def given_all_correct_responses(ctx):
    n = len(ctx["dataset"].test_cases)
    ctx["chat_results"] = [
        _make_chat_result(answer="這是正確的回答") for _ in range(n)
    ]


@when("我執行評估", target_fixture="summary")
def when_evaluate(ctx) -> DatasetEvalSummary:
    evaluator = Evaluator()
    return evaluator.evaluate(ctx["dataset"], ctx["chat_results"])


@then("quality_score 應為 1.0")
def then_quality_score_1(summary: DatasetEvalSummary):
    assert summary.quality_score == pytest.approx(1.0)


@then("所有 case 都應通過")
def then_all_passed(summary: DatasetEvalSummary):
    for cr in summary.case_results:
        assert cr.score == pytest.approx(1.0), f"Case {cr.case_id} score={cr.score}"
        assert not cr.p0_failed


# ═══════════════════════════════════════════════════════════════
# Scenario: P0 hard-fail
# ═══════════════════════════════════════════════════════════════


@given("一個包含 P0 assertion 的 test case")
def given_p0_case(ctx):
    cases = (
        TestCase(
            id="tc-p0",
            question="P0 問題",
            priority="P0",
            category="critical",
            assertions=(
                Assertion(type="contains_all", params={"keywords": ["不存在的關鍵字"]}),
                Assertion(type="response_not_empty"),
            ),
        ),
        TestCase(
            id="tc-p1-pass",
            question="P1 問題",
            priority="P1",
            category="general",
            assertions=(Assertion(type="response_not_empty"),),
        ),
    )
    ctx["dataset"] = _make_dataset(cases)


@given("P0 assertion 失敗")
def given_p0_fails(ctx):
    # First case answer does NOT contain "不存在的關鍵字" → P0 fails
    ctx["chat_results"] = [
        _make_chat_result(answer="一般回答"),
        _make_chat_result(answer="正常回答"),
    ]


@then("該 case 的 score 應為 0.0")
def then_case_score_0(summary: DatasetEvalSummary):
    p0_case = next(cr for cr in summary.case_results if cr.priority == "P0")
    assert p0_case.score == pytest.approx(0.0)
    assert p0_case.p0_failed


@then("overall quality_score 應低於 1.0")
def then_overall_below_1(summary: DatasetEvalSummary):
    assert summary.quality_score < 1.0
    assert len(summary.p0_failures) > 0


# ═══════════════════════════════════════════════════════════════
# Scenario: 混合 P0/P1/P2 加權評分
# ═══════════════════════════════════════════════════════════════


@given("一個包含 P0 P1 P2 各一個 case 的 dataset")
def given_mixed_priority(ctx):
    cases = (
        TestCase(
            id="tc-p0",
            question="P0 問題",
            priority="P0",
            category="critical",
            assertions=(Assertion(type="response_not_empty"),),
        ),
        TestCase(
            id="tc-p1",
            question="P1 問題",
            priority="P1",
            category="general",
            assertions=(
                Assertion(type="response_not_empty"),
                Assertion(type="contains_all", params={"keywords": ["找不到"]}),
            ),
        ),
        TestCase(
            id="tc-p2",
            question="P2 問題",
            priority="P2",
            category="nice-to-have",
            assertions=(Assertion(type="response_not_empty"),),
        ),
    )
    ctx["dataset"] = _make_dataset(cases)


@given("P1 case 部分通過")
def given_p1_partial(ctx):
    ctx["chat_results"] = [
        _make_chat_result(answer="P0 通過"),       # P0: all pass → score=1.0
        _make_chat_result(answer="P1 部分通過"),    # P1: 1/2 pass (response_not_empty passes, contains_all fails)
        _make_chat_result(answer="P2 通過"),       # P2: all pass → score=1.0
    ]


@then("quality_score 應根據優先權加權計算")
def then_weighted_score(summary: DatasetEvalSummary):
    # P0 score=1.0 weight=3.0, P1 score=0.5 weight=2.0, P2 score=1.0 weight=1.0
    expected = (1.0 * 3.0 + 0.5 * 2.0 + 1.0 * 1.0) / (3.0 + 2.0 + 1.0)
    assert summary.quality_score == pytest.approx(expected)
    # Verify P1 case score
    p1_case = next(cr for cr in summary.case_results if cr.priority == "P1")
    assert p1_case.score == pytest.approx(0.5)


# ═══════════════════════════════════════════════════════════════
# Scenario: 成本感知評分
# ═══════════════════════════════════════════════════════════════


@given("一個包含 cost_config 的 dataset")
def given_cost_config(ctx):
    cost_cfg = CostConfigData(
        token_budget=1000,
        quality_weight=0.80,
        cost_weight=0.20,
    )
    cases = (
        TestCase(
            id="tc-cost",
            question="成本測試",
            priority="P1",
            category="cost",
            assertions=(Assertion(type="response_not_empty"),),
        ),
    )
    ctx["dataset"] = _make_dataset(cases, cost_config=cost_cfg)


@given("API 回應含 usage 資訊")
def given_usage_info(ctx):
    ctx["chat_results"] = [
        _make_chat_result(
            answer="回答",
            usage={
                "input_tokens": 200,
                "output_tokens": 300,
                "total_tokens": 500,
                "estimated_cost": 0.005,
            },
        ),
    ]


@then("final_score 應結合 quality 和 cost 分數")
def then_final_score_combined(summary: DatasetEvalSummary):
    # quality=1.0, avg_tokens=500, budget=1000 → cost_score=0.5
    # final = 0.80*1.0 + 0.20*0.5 = 0.9
    assert summary.quality_score == pytest.approx(1.0)
    assert summary.avg_total_tokens == 500
    assert summary.cost_score == pytest.approx(0.5)
    assert summary.final_score == pytest.approx(0.9)
    assert summary.total_run_cost == pytest.approx(0.005)


# ═══════════════════════════════════════════════════════════════
# Scenario: 空回應處理
# ═══════════════════════════════════════════════════════════════


@given("一個 test case")
def given_single_case(ctx):
    cases = (
        TestCase(
            id="tc-empty",
            question="空回應測試",
            priority="P1",
            category="edge",
            assertions=(
                Assertion(type="response_not_empty"),
                Assertion(type="max_length", params={"max_chars": 500}),
            ),
        ),
    )
    ctx["dataset"] = _make_dataset(cases)


@given("API 回應為空字串")
def given_empty_response(ctx):
    ctx["chat_results"] = [_make_chat_result(answer="")]


@then("該 case 應標記為 api_error 且 score 為 0")
def then_empty_response_assertions(summary: DatasetEvalSummary):
    case = summary.case_results[0]
    # Empty response → api_error short-circuit, score=0.0
    assert case.total_count == 2
    assert len(case.assertion_results) == 1
    assert case.assertion_results[0].assertion_type == "api_error"
    assert case.assertion_results[0].passed is False
    assert case.score == pytest.approx(0.0)
