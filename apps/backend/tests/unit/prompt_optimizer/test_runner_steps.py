"""Prompt Optimizer Karpathy Loop Runner BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from prompt_optimizer.api_client import ChatResult
from prompt_optimizer.config import OptimizationConfig, PromptTarget
from prompt_optimizer.dataset import (
    Assertion,
    CostConfigData,
    Dataset,
    DatasetMetadata,
    TestCase,
)
from prompt_optimizer.evaluator import Evaluator
from prompt_optimizer.runner import KarpathyLoopRunner, RunResult

scenarios("unit/prompt_optimizer/runner.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

INITIAL_PROMPT = "你是一個客服助手，請回答用戶的問題。"


def _make_chat_result(
    answer: str = "這是正確的回答",
    usage: dict | None = None,
    latency_ms: int = 100,
) -> ChatResult:
    return ChatResult(
        answer=answer,
        conversation_id="conv-test",
        tool_calls=[],
        sources=[],
        usage=usage,
        latency_ms=latency_ms,
    )


def _make_dataset(
    num_cases: int = 2,
    cost_config: CostConfigData | None = None,
) -> Dataset:
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
        for i in range(1, num_cases + 1)
    )
    return Dataset(
        metadata=DatasetMetadata(
            tenant_id="t-1",
            bot_id="b-1",
            cost_config=cost_config or CostConfigData(),
        ),
        test_cases=cases,
    )


@pytest.fixture
def ctx():
    return {}


# ═══════════════════════════════════════════════════════════════
# Shared Given steps
# ═══════════════════════════════════════════════════════════════


@given("一個 dataset 和初始 prompt")
def given_dataset_and_prompt(ctx):
    ctx["dataset"] = _make_dataset(num_cases=2)
    ctx["initial_prompt"] = INITIAL_PROMPT
    ctx["db_read"] = MagicMock(return_value=INITIAL_PROMPT)
    ctx["db_write"] = MagicMock()
    ctx["api_client"] = AsyncMock()
    ctx["mutator"] = AsyncMock()


# ═══════════════════════════════════════════════════════════════
# Scenario: 正常完成優化迴圈
# ═══════════════════════════════════════════════════════════════


@given("mutator 會產出改進的 prompt")
def given_mutator_produces_improved(ctx):
    # Each mutation returns a different improved prompt
    ctx["mutator"].mutate = AsyncMock(
        side_effect=[
            "改進版 prompt v1",
            "改進版 prompt v2",
            "改進版 prompt v3",
            "改進版 prompt v4",
            "改進版 prompt v5",
        ]
    )


@given("評估分數持續提升")
def given_scores_improve(ctx):
    """Configure api_client.chat to return progressively better answers.

    Baseline: answer without keyword -> partial score
    Iteration 1+: answers with keyword -> higher score
    """
    num_cases = len(ctx["dataset"].test_cases)
    call_count = 0

    async def improving_chat(**kwargs):
        nonlocal call_count
        batch = call_count // num_cases  # 0=baseline, 1=iter1, ...
        call_count += 1
        if batch == 0:
            # Baseline: only response_not_empty passes (no keyword "回答")
            return _make_chat_result(answer="一般回覆")
        else:
            # Iterations: both assertions pass
            return _make_chat_result(answer="這是正確的回答")

    ctx["api_client"].chat = AsyncMock(side_effect=improving_chat)


@when("我執行優化迴圈 最多 5 輪")
def when_run_optimization_5(ctx):
    config = OptimizationConfig(
        target=PromptTarget(level="bot", field="system_prompt", bot_id="b-1"),
        max_iterations=5,
        patience=5,
        budget=200,
    )
    runner = KarpathyLoopRunner(
        api_client=ctx["api_client"],
        db_read_prompt=ctx["db_read"],
        db_write_prompt=ctx["db_write"],
        evaluator=Evaluator(),
        mutator=ctx["mutator"],
    )
    ctx["result"] = _run(runner.run(config, ctx["dataset"], run_id="test-run"))


@then("最終 prompt 應是分數最高的版本")
def then_best_prompt(ctx):
    result: RunResult = ctx["result"]
    # Best prompt should be one of the improved versions (not the initial)
    assert result.best_prompt != INITIAL_PROMPT
    assert result.best_score > result.baseline_score


@then("迭代次數應大於 1")
def then_iterations_gt_1(ctx):
    result: RunResult = ctx["result"]
    # iterations includes iteration 0 (baseline), so len > 2 means at least 1 mutation
    assert len(result.iterations) > 1


# ═══════════════════════════════════════════════════════════════
# Scenario: Patience 機制觸發 early stop
# ═══════════════════════════════════════════════════════════════


@given("分數連續 3 輪未改善")
def given_scores_stagnate(ctx):
    """Mutator returns new prompts but scores don't improve."""
    ctx["mutator"].mutate = AsyncMock(
        side_effect=[f"嘗試 prompt v{i}" for i in range(1, 11)]
    )
    num_cases = len(ctx["dataset"].test_cases)

    # All calls return the same mediocre answer → score never improves
    async def same_score_chat(**kwargs):
        return _make_chat_result(answer="一般回覆不含關鍵字")

    ctx["api_client"].chat = AsyncMock(side_effect=same_score_chat)


@when("我執行優化迴圈 patience 為 3")
def when_run_patience_3(ctx):
    config = OptimizationConfig(
        target=PromptTarget(level="bot", field="system_prompt", bot_id="b-1"),
        max_iterations=20,
        patience=3,
        budget=200,
    )
    runner = KarpathyLoopRunner(
        api_client=ctx["api_client"],
        db_read_prompt=ctx["db_read"],
        db_write_prompt=ctx["db_write"],
        evaluator=Evaluator(),
        mutator=ctx["mutator"],
    )
    ctx["result"] = _run(runner.run(config, ctx["dataset"], run_id="patience-test"))


@then("應提前停止")
def then_early_stop(ctx):
    result: RunResult = ctx["result"]
    assert result.stopped_reason == "patience"
    # Should have stopped after 3 non-improving iterations (baseline + 3 iterations = 4 total)
    assert len(result.iterations) == 4  # iteration 0,1,2,3


@then("最終 prompt 應是最佳版本")
def then_final_is_best(ctx):
    result: RunResult = ctx["result"]
    # Since no improvement, best prompt should still be the initial one
    assert result.best_prompt == INITIAL_PROMPT
    assert result.best_score == result.baseline_score


# ═══════════════════════════════════════════════════════════════
# Scenario: Budget 上限停止
# ═══════════════════════════════════════════════════════════════


@given("一個 dataset 和初始 prompt 含 3 個 cases")
def given_dataset_3_cases(ctx):
    ctx["dataset"] = _make_dataset(num_cases=3)
    ctx["initial_prompt"] = INITIAL_PROMPT
    ctx["db_read"] = MagicMock(return_value=INITIAL_PROMPT)
    ctx["db_write"] = MagicMock()
    ctx["api_client"] = AsyncMock()
    ctx["mutator"] = AsyncMock()
    ctx["mutator"].mutate = AsyncMock(
        side_effect=[f"budget prompt v{i}" for i in range(1, 11)]
    )
    # All calls return same answer
    ctx["api_client"].chat = AsyncMock(
        return_value=_make_chat_result(answer="一般回覆")
    )


@when("我執行優化迴圈 budget 為 6")
def when_run_budget_6(ctx):
    config = OptimizationConfig(
        target=PromptTarget(level="bot", field="system_prompt", bot_id="b-1"),
        max_iterations=20,
        patience=20,
        budget=6,  # 3 cases/iter → baseline uses 3, only 1 more iteration fits
    )
    runner = KarpathyLoopRunner(
        api_client=ctx["api_client"],
        db_read_prompt=ctx["db_read"],
        db_write_prompt=ctx["db_write"],
        evaluator=Evaluator(),
        mutator=ctx["mutator"],
    )
    ctx["result"] = _run(runner.run(config, ctx["dataset"], run_id="budget-test"))


@then("應在 budget 耗盡後停止")
def then_budget_exhausted(ctx):
    result: RunResult = ctx["result"]
    assert result.stopped_reason == "budget"
    # Baseline uses 3 API calls. Budget=6, so only 1 iteration possible (3+3=6).
    # After iteration 1 (total_api_calls=6), next iteration needs 3 more (6+3=9 > 6) → stop.
    assert result.total_api_calls <= 6
    # iterations: baseline (0) + 1 iteration
    assert len(result.iterations) == 2


# ═══════════════════════════════════════════════════════════════
# Scenario: Dry run 只評估不變更
# ═══════════════════════════════════════════════════════════════


@when("我以 dry_run 模式執行")
def when_dry_run(ctx):
    # For dry run, api_client needs to return results for baseline eval
    num_cases = len(ctx["dataset"].test_cases)
    ctx["api_client"].chat = AsyncMock(
        return_value=_make_chat_result(answer="這是正確的回答")
    )

    config = OptimizationConfig(
        target=PromptTarget(level="bot", field="system_prompt", bot_id="b-1"),
        max_iterations=10,
        patience=5,
        budget=200,
        dry_run=True,
    )
    runner = KarpathyLoopRunner(
        api_client=ctx["api_client"],
        db_read_prompt=ctx["db_read"],
        db_write_prompt=ctx["db_write"],
        evaluator=Evaluator(),
        mutator=ctx["mutator"],
    )
    ctx["result"] = _run(runner.run(config, ctx["dataset"], run_id="dry-run-test"))


@then("只回傳 baseline 評估結果")
def then_only_baseline(ctx):
    result: RunResult = ctx["result"]
    assert result.stopped_reason == "dry_run"
    assert len(result.iterations) == 1
    assert result.iterations[0].iteration == 0


@then("prompt 不應被修改")
def then_prompt_not_modified(ctx):
    result: RunResult = ctx["result"]
    # db_write should never be called in dry_run mode
    ctx["db_write"].assert_not_called()
    # mutator should never be called
    ctx["mutator"].mutate.assert_not_called()
    # best prompt should be the initial prompt
    assert result.best_prompt == INITIAL_PROMPT
