"""BDD step definitions for Validation Evaluator."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from prompt_optimizer.api_client import ChatResult
from prompt_optimizer.dataset import Assertion, CostConfigData, Dataset, DatasetMetadata, TestCase
from prompt_optimizer.evaluator import Evaluator
from prompt_optimizer.validation_evaluator import ValidationEvaluator

scenarios("unit/prompt_optimizer/validation_evaluator.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_chat_result(passed: bool) -> ChatResult:
    """Create a ChatResult that will pass or fail a contains_any assertion."""
    return ChatResult(
        answer="包含關鍵字" if passed else "完全無關的回覆",
        conversation_id="conv-1",
        tool_calls=[],
        sources=[],
        usage={"total_tokens": 100, "input_tokens": 50, "output_tokens": 50, "estimated_cost": 0.01},
        latency_ms=200,
    )


def _make_assertion() -> Assertion:
    return Assertion(type="contains_any", params={"keywords": ["關鍵字"]})


@pytest.fixture
def context():
    return {}


@given("一個 Evaluator 實例")
def setup_evaluator(context):
    context["evaluator"] = Evaluator()
    context["validator"] = ValidationEvaluator(evaluator=context["evaluator"])


@given("一個含有 2 個 P1 case 的 dataset")
def dataset_2_p1(context):
    context["dataset"] = Dataset(
        metadata=DatasetMetadata(tenant_id="t1", agent_mode="router"),
        test_cases=(
            TestCase(id="case-1", question="Q1", priority="P1", assertions=(_make_assertion(),)),
            TestCase(id="case-2", question="Q2", priority="P1", assertions=(_make_assertion(),)),
        ),
    )


@given("一個含有 1 個 P0 case 和 1 個 P1 case 的 dataset")
def dataset_p0_p1(context):
    context["dataset"] = Dataset(
        metadata=DatasetMetadata(tenant_id="t1", agent_mode="router"),
        test_cases=(
            TestCase(id="p0-case", question="Q-P0", priority="P0", assertions=(_make_assertion(),)),
            TestCase(id="p1-case", question="Q-P1", priority="P1", assertions=(_make_assertion(),)),
        ),
    )


@given("一個含有 1 個 P1 case 的 dataset")
def dataset_1_p1(context):
    context["dataset"] = Dataset(
        metadata=DatasetMetadata(tenant_id="t1", agent_mode="router"),
        test_cases=(
            TestCase(id="p1-case", question="Q-P1", priority="P1", assertions=(_make_assertion(),)),
        ),
    )


@given("一個含有 1 個 P2 case 的 dataset")
def dataset_1_p2(context):
    context["dataset"] = Dataset(
        metadata=DatasetMetadata(tenant_id="t1", agent_mode="router"),
        test_cases=(
            TestCase(id="p2-case", question="Q-P2", priority="P2", assertions=(_make_assertion(),)),
        ),
    )


@given("eval_fn 每次回傳所有 assertions 全部通過")
def eval_fn_all_pass(context):
    num_cases = len(context["dataset"].test_cases)
    context["eval_fn"] = AsyncMock(
        return_value=[_make_chat_result(passed=True) for _ in range(num_cases)]
    )


@given("eval_fn 對 P0 case 在第 2 次回傳 fail")
def eval_fn_p0_fail_on_run2(context):
    call_count = {"n": 0}

    async def _eval_fn():
        call_count["n"] += 1
        run = call_count["n"]
        # P0 case fails on run 2, P1 case always passes
        p0_result = _make_chat_result(passed=(run != 2))
        p1_result = _make_chat_result(passed=True)
        return [p0_result, p1_result]

    context["eval_fn"] = _eval_fn


@given("eval_fn 對 P1 case 在 5 次中有 4 次全通過")
def eval_fn_p1_4_of_5(context):
    call_count = {"n": 0}

    async def _eval_fn():
        call_count["n"] += 1
        run = call_count["n"]
        return [_make_chat_result(passed=(run != 3))]  # fail on run 3

    context["eval_fn"] = _eval_fn


@given("eval_fn 對 P1 case 在 5 次中有 3 次全通過")
def eval_fn_p1_3_of_5(context):
    call_count = {"n": 0}

    async def _eval_fn():
        call_count["n"] += 1
        run = call_count["n"]
        return [_make_chat_result(passed=(run <= 3))]  # pass runs 1-3, fail 4-5

    context["eval_fn"] = _eval_fn


@given("eval_fn 對 P2 case 在 5 次中有 3 次全通過")
def eval_fn_p2_3_of_5(context):
    call_count = {"n": 0}

    async def _eval_fn():
        call_count["n"] += 1
        run = call_count["n"]
        return [_make_chat_result(passed=(run <= 3))]

    context["eval_fn"] = _eval_fn


@when("執行驗收評估 repeats=1", target_fixture="result")
def run_validation_1(context):
    return _run(
        context["validator"].validate(context["dataset"], context["eval_fn"], n_repeats=1)
    )


@when("執行驗收評估 repeats=5", target_fixture="result")
def run_validation_5(context):
    return _run(
        context["validator"].validate(context["dataset"], context["eval_fn"], n_repeats=5)
    )


@when("執行驗收評估 repeats=3", target_fixture="result")
def run_validation_3(context):
    return _run(
        context["validator"].validate(context["dataset"], context["eval_fn"], n_repeats=3)
    )


@then('verdict 應為 "PASS"')
def check_pass(result):
    assert result.verdict == "PASS"


@then('verdict 應為 "FAIL"')
def check_fail(result):
    assert result.verdict == "FAIL"


@then("passed_cases 應為 2")
def check_passed_2(result):
    assert result.passed_cases == 2


@then("failed_cases 應為 0")
def check_failed_0(result):
    assert result.failed_cases == 0


@then("P0 case 的 pass_rate 應為 0.8")
def check_p0_pass_rate(result):
    p0 = next(c for c in result.case_results if c.priority == "P0")
    assert p0.pass_rate == 0.8


@then("P0 case 的 passed 應為 false")
def check_p0_not_passed(result):
    p0 = next(c for c in result.case_results if c.priority == "P0")
    assert p0.passed is False


@then("p0_failures 應包含該 P0 case_id")
def check_p0_failures(result):
    assert "p0-case" in result.p0_failures


@then("P1 case 的 pass_rate 應為 0.8")
def check_p1_pass_rate_08(result):
    p1 = next(c for c in result.case_results if c.priority == "P1")
    assert p1.pass_rate == 0.8


@then("P1 case 的 pass_rate 應為 0.6")
def check_p1_pass_rate_06(result):
    p1 = next(c for c in result.case_results if c.priority == "P1")
    assert p1.pass_rate == 0.6


@then("P1 case 的 passed 應為 true")
def check_p1_passed(result):
    p1 = next(c for c in result.case_results if c.priority == "P1")
    assert p1.passed is True


@then("P1 case 的 passed 應為 false")
def check_p1_not_passed(result):
    p1 = next(c for c in result.case_results if c.priority == "P1")
    assert p1.passed is False


@then("P2 case 的 pass_rate 應為 0.6")
def check_p2_pass_rate_06(result):
    p2 = next(c for c in result.case_results if c.priority == "P2")
    assert p2.pass_rate == 0.6


@then("P2 case 的 passed 應為 true")
def check_p2_passed(result):
    p2 = next(c for c in result.case_results if c.priority == "P2")
    assert p2.passed is True


@then("P1 case 的 unstable 應為 true")
def check_p1_unstable(result):
    p1 = next(c for c in result.case_results if c.priority == "P1")
    assert p1.unstable is True


@then("P1 case 的 unstable 應為 false")
def check_p1_stable(result):
    p1 = next(c for c in result.case_results if c.priority == "P1")
    assert p1.unstable is False
