from __future__ import annotations

import logging
from dataclasses import dataclass, field

from prompt_optimizer.api_client import ChatResult
from prompt_optimizer.assertions import AssertionContext, AssertionResult, run_assertion
from prompt_optimizer.dataset import CostConfigData, Dataset, TestCase

logger = logging.getLogger(__name__)

# Priority weights for scoring
PRIORITY_WEIGHTS = {"P0": 3.0, "P1": 2.0, "P2": 1.0}


@dataclass
class CaseResult:
    case_id: str
    question: str
    priority: str
    category: str
    score: float  # 0.0 if P0 hard-fail, else passed/total
    passed_count: int
    total_count: int
    assertion_results: list[AssertionResult]
    p0_failed: bool = False
    answer_snippet: str = ""  # first 200 chars for reporting


@dataclass
class DatasetEvalSummary:
    quality_score: float  # weighted avg of case scores (0-1)
    avg_total_tokens: int = 0
    avg_cost_per_call: float = 0.0
    total_run_cost: float = 0.0
    cost_score: float = 1.0  # cost efficiency (0-1)
    final_score: float = 0.0  # quality_weight * quality + cost_weight * cost
    case_results: list[CaseResult] = field(default_factory=list)
    p0_failures: list[str] = field(default_factory=list)  # case IDs with P0 failures


def calculate_final_score(
    quality_score: float,
    avg_tokens: int,
    token_budget: int,
    quality_weight: float = 0.85,
    cost_weight: float = 0.15,
) -> float:
    """Calculate final score combining quality and cost efficiency."""
    if token_budget <= 0:
        return quality_score
    cost_score = max(0.0, 1.0 - (avg_tokens / token_budget))
    return quality_weight * quality_score + cost_weight * cost_score


@dataclass
class ValidationCaseResult:
    """Per-case result from N-repeat validation evaluation."""

    case_id: str
    question: str
    priority: str  # P0 / P1 / P2
    pass_rate: float  # 0.0 ~ 1.0
    threshold: float  # P0=1.0, P1=0.8, P2=0.6
    passed: bool  # pass_rate >= threshold
    run_scores: list[float] = field(default_factory=list)  # per-run case scores
    unstable: bool = False  # passed but pass_rate < 1.0


@dataclass
class ValidationSummary:
    """Aggregated result from N-repeat validation evaluation."""

    verdict: str  # "PASS" | "FAIL"
    num_repeats: int
    total_cases: int
    passed_cases: int
    failed_cases: int
    unstable_cases: int  # passed but not 100%
    case_results: list[ValidationCaseResult] = field(default_factory=list)
    p0_failures: list[str] = field(default_factory=list)  # P0 case IDs that failed


# Validation pass rate thresholds per priority
VALIDATION_THRESHOLDS = {"P0": 1.0, "P1": 0.8, "P2": 0.6}


class Evaluator:
    """Runs binary assertions against API responses and computes scores."""

    def evaluate(
        self,
        dataset: Dataset,
        chat_results: list[ChatResult],
        cost_config: CostConfigData | None = None,
    ) -> DatasetEvalSummary:
        """Evaluate chat results against dataset test cases.

        Args:
            dataset: The eval dataset with test cases and assertions
            chat_results: API responses, one per test case (same order)
            cost_config: Optional cost configuration for cost-aware scoring
        """
        if len(dataset.test_cases) != len(chat_results):
            raise ValueError(
                f"Mismatch: {len(dataset.test_cases)} cases vs {len(chat_results)} results"
            )

        case_results: list[CaseResult] = []
        p0_failures: list[str] = []
        total_tokens_sum = 0
        total_cost_sum = 0.0

        for tc, cr in zip(dataset.test_cases, chat_results, strict=True):
            case_result = self._evaluate_case(tc, cr)
            case_results.append(case_result)
            if case_result.p0_failed:
                p0_failures.append(tc.id)

            # Accumulate cost data
            if cr.usage:
                total_tokens_sum += cr.usage.get("total_tokens", 0)
                total_cost_sum += cr.usage.get("estimated_cost", 0.0)

        # Calculate quality score (weighted average)
        quality_score = self._weighted_quality_score(case_results)

        # Calculate cost metrics
        n = len(chat_results)
        avg_total_tokens = total_tokens_sum // n if n > 0 else 0
        avg_cost_per_call = total_cost_sum / n if n > 0 else 0.0

        # Calculate final score with cost
        effective_cost_config = cost_config or dataset.metadata.cost_config

        token_budget = effective_cost_config.token_budget
        cost_score = (
            max(0.0, 1.0 - (avg_total_tokens / token_budget))
            if token_budget > 0
            else 1.0
        )
        final_score = calculate_final_score(
            quality_score,
            avg_total_tokens,
            token_budget,
            effective_cost_config.quality_weight,
            effective_cost_config.cost_weight,
        )

        return DatasetEvalSummary(
            quality_score=quality_score,
            avg_total_tokens=avg_total_tokens,
            avg_cost_per_call=avg_cost_per_call,
            total_run_cost=total_cost_sum,
            cost_score=cost_score,
            final_score=final_score,
            case_results=case_results,
            p0_failures=p0_failures,
        )

    def _evaluate_case(self, tc: TestCase, cr: ChatResult) -> CaseResult:
        """Evaluate a single test case against its chat result."""
        ctx = AssertionContext(
            response_text=cr.answer,
            tool_calls=cr.tool_calls,
            sources=cr.sources,
            user_message=tc.question,
            conversation_history=list(tc.conversation_history),
            latency_ms=cr.latency_ms,
            input_tokens=cr.usage.get("input_tokens", 0) if cr.usage else 0,
            output_tokens=cr.usage.get("output_tokens", 0) if cr.usage else 0,
            total_tokens=cr.usage.get("total_tokens", 0) if cr.usage else 0,
            estimated_cost=cr.usage.get("estimated_cost", 0.0) if cr.usage else 0.0,
        )

        assertion_results: list[AssertionResult] = []
        for assertion in tc.assertions:
            result = run_assertion(assertion.type, ctx, assertion.params)
            assertion_results.append(result)

        # Check P0 hard-fail
        p0_failed = False
        if tc.priority == "P0":
            if any(not r.passed for r in assertion_results):
                p0_failed = True

        # Calculate case score
        if p0_failed:
            score = 0.0
        else:
            passed = sum(1 for r in assertion_results if r.passed)
            total = len(assertion_results)
            score = passed / total if total > 0 else 1.0

        return CaseResult(
            case_id=tc.id,
            question=tc.question,
            priority=tc.priority,
            category=tc.category,
            score=score,
            passed_count=sum(1 for r in assertion_results if r.passed),
            total_count=len(assertion_results),
            assertion_results=assertion_results,
            p0_failed=p0_failed,
            answer_snippet=cr.answer[:200],
        )

    def _weighted_quality_score(self, case_results: list[CaseResult]) -> float:
        """Calculate priority-weighted average of case scores."""
        total_weight = 0.0
        weighted_sum = 0.0
        for cr in case_results:
            w = PRIORITY_WEIGHTS.get(cr.priority, 1.0)
            weighted_sum += cr.score * w
            total_weight += w
        return weighted_sum / total_weight if total_weight > 0 else 0.0
