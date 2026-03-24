"""Validation Evaluator — run N evaluations and aggregate pass rates."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from prompt_optimizer.api_client import ChatResult
from prompt_optimizer.dataset import Dataset
from prompt_optimizer.evaluator import (
    VALIDATION_THRESHOLDS,
    DatasetEvalSummary,
    Evaluator,
    ValidationCaseResult,
    ValidationSummary,
)

logger = logging.getLogger(__name__)


class ValidationEvaluator:
    """Run N evaluations of the same prompt and produce a PASS/FAIL verdict."""

    def __init__(self, evaluator: Evaluator | None = None):
        self._evaluator = evaluator or Evaluator()

    async def validate(
        self,
        dataset: Dataset,
        eval_fn: Callable[[], Awaitable[list[ChatResult]]],
        n_repeats: int,
    ) -> ValidationSummary:
        """Run eval_fn N times, aggregate per-case pass rates, return verdict.

        Args:
            dataset: The eval dataset with test cases and assertions
            eval_fn: Async callable that returns ChatResult list (one per test case)
            n_repeats: Number of times to repeat the evaluation
        """
        if n_repeats < 1:
            raise ValueError("n_repeats must be >= 1")

        # Run N evaluations
        summaries: list[DatasetEvalSummary] = []
        for i in range(n_repeats):
            logger.info("Validation run %d/%d", i + 1, n_repeats)
            chat_results = await eval_fn()
            summary = self._evaluator.evaluate(dataset, chat_results)
            summaries.append(summary)

        # Aggregate per-case results
        case_results: list[ValidationCaseResult] = []
        p0_failures: list[str] = []

        for case_idx, tc in enumerate(dataset.test_cases):
            # Collect this case's score from each run
            run_scores = [s.case_results[case_idx].score for s in summaries]

            # A case "fully passes" a run if score == 1.0
            full_pass_count = sum(1 for s in run_scores if s >= 1.0)
            pass_rate = full_pass_count / n_repeats

            threshold = VALIDATION_THRESHOLDS.get(tc.priority, 0.6)
            passed = pass_rate >= threshold
            unstable = passed and pass_rate < 1.0

            if tc.priority == "P0" and not passed:
                p0_failures.append(tc.id)

            case_results.append(
                ValidationCaseResult(
                    case_id=tc.id,
                    question=tc.question,
                    priority=tc.priority,
                    pass_rate=round(pass_rate, 4),
                    threshold=threshold,
                    passed=passed,
                    run_scores=run_scores,
                    unstable=unstable,
                )
            )

        passed_cases = sum(1 for c in case_results if c.passed)
        failed_cases = sum(1 for c in case_results if not c.passed)
        unstable_cases = sum(1 for c in case_results if c.unstable)
        verdict = "PASS" if failed_cases == 0 else "FAIL"

        return ValidationSummary(
            verdict=verdict,
            num_repeats=n_repeats,
            total_cases=len(case_results),
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            unstable_cases=unstable_cases,
            case_results=case_results,
            p0_failures=p0_failures,
        )
