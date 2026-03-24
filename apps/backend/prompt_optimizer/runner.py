from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from prompt_optimizer.api_client import AgentAPIClient, ChatResult
from prompt_optimizer.config import OptimizationConfig, PromptTarget
from prompt_optimizer.dataset import Dataset
from prompt_optimizer.evaluator import DatasetEvalSummary, Evaluator
from prompt_optimizer.mutator import CostStats, FailedCase, PromptMutator

logger = logging.getLogger(__name__)


@dataclass
class IterationResult:
    iteration: int
    prompt_snapshot: str
    eval_summary: DatasetEvalSummary
    is_best: bool = False
    accepted: bool = False  # score improved → accepted


@dataclass
class RunResult:
    run_id: str
    target: PromptTarget
    baseline_score: float
    best_score: float
    best_prompt: str
    iterations: list[IterationResult] = field(default_factory=list)
    total_api_calls: int = 0
    stopped_reason: str = (
        ""  # "converged" | "patience" | "budget" | "max_iterations" | "dry_run"
    )


class KarpathyLoopRunner:
    """Orchestrates the Karpathy Loop: eval → mutate → eval → keep/discard."""

    def __init__(
        self,
        api_client: AgentAPIClient,
        db_read_prompt: Any,  # callable: (PromptTarget) -> str
        db_write_prompt: Any,  # callable: (PromptTarget, str) -> None
        evaluator: Evaluator | None = None,
        mutator: PromptMutator | None = None,
    ):
        self._api = api_client
        self._read_prompt = db_read_prompt
        self._write_prompt = db_write_prompt
        self._evaluator = evaluator or Evaluator()
        self._mutator = mutator or PromptMutator()

    async def run(
        self, config: OptimizationConfig, dataset: Dataset, run_id: str = ""
    ) -> RunResult:
        """Execute the Karpathy optimization loop."""
        import uuid

        if not run_id:
            run_id = str(uuid.uuid4())

        target = config.target

        # 1. Read baseline prompt
        baseline_prompt = self._read_prompt(target)
        logger.info("Baseline prompt loaded (%d chars)", len(baseline_prompt))

        # 2. Eval baseline
        baseline_results = await self._eval_all(dataset, config)
        baseline_summary = self._evaluator.evaluate(
            dataset, baseline_results, dataset.metadata.cost_config
        )
        baseline_score = baseline_summary.final_score

        result = RunResult(
            run_id=run_id,
            target=target,
            baseline_score=baseline_score,
            best_score=baseline_score,
            best_prompt=baseline_prompt,
            total_api_calls=len(dataset.test_cases),
        )

        # Record baseline as iteration 0
        result.iterations.append(
            IterationResult(
                iteration=0,
                prompt_snapshot=baseline_prompt,
                eval_summary=baseline_summary,
                is_best=True,
                accepted=True,
            )
        )

        logger.info("Baseline score: %.4f", baseline_score)

        # Dry run: stop here
        if config.dry_run:
            result.stopped_reason = "dry_run"
            return result

        # 3. Optimization loop
        best_prompt = baseline_prompt
        best_score = baseline_score
        no_improve_count = 0
        temperature = 0.7

        for i in range(1, config.max_iterations + 1):
            # Check budget
            if result.total_api_calls + len(dataset.test_cases) > config.budget:
                result.stopped_reason = "budget"
                logger.info("Budget exhausted at iteration %d", i)
                break

            # Mutate
            failed_cases = self._extract_failed_cases(
                result.iterations[-1].eval_summary
            )
            cost_stats = self._extract_cost_stats(
                result.iterations[-1].eval_summary, dataset
            )

            candidate = await self._mutator.mutate(
                current_prompt=best_prompt,
                failed_cases=failed_cases,
                iteration=i,
                cost_stats=cost_stats,
                temperature=temperature,
            )

            # Write candidate to DB
            self._write_prompt(target, candidate)

            # Eval candidate
            eval_results = await self._eval_all(dataset, config)
            result.total_api_calls += len(dataset.test_cases)
            eval_summary = self._evaluator.evaluate(
                dataset, eval_results, dataset.metadata.cost_config
            )
            score = eval_summary.final_score

            # Accept or discard
            accepted = score > best_score
            is_best = accepted
            if accepted:
                best_score = score
                best_prompt = candidate
                no_improve_count = 0
                temperature = 0.7  # Reset temperature on improvement
                logger.info("Iteration %d: %.4f → ACCEPTED (new best)", i, score)
            else:
                no_improve_count += 1
                temperature = min(temperature + 0.1, 1.5)  # Escalate temperature
                logger.info(
                    "Iteration %d: %.4f → DISCARDED (no improve %d/%d)",
                    i,
                    score,
                    no_improve_count,
                    config.patience,
                )

            result.iterations.append(
                IterationResult(
                    iteration=i,
                    prompt_snapshot=candidate,
                    eval_summary=eval_summary,
                    is_best=is_best,
                    accepted=accepted,
                )
            )

            # Early stop: perfect score
            if best_score >= 1.0:
                result.stopped_reason = "converged"
                logger.info("Perfect score reached at iteration %d", i)
                break

            # Early stop: patience
            if no_improve_count >= config.patience:
                result.stopped_reason = "patience"
                logger.info("Patience exhausted at iteration %d", i)
                break
        else:
            result.stopped_reason = "max_iterations"

        # Finalize: write best prompt to DB
        self._write_prompt(target, best_prompt)
        result.best_score = best_score
        result.best_prompt = best_prompt

        logger.info(
            "Optimization complete: %.4f → %.4f (%s)",
            baseline_score,
            best_score,
            result.stopped_reason,
        )
        return result

    async def _eval_all(
        self, dataset: Dataset, config: OptimizationConfig
    ) -> list[ChatResult]:
        """Evaluate all test cases via API."""
        results = []
        for tc in dataset.test_cases:
            try:
                cr = await self._api.chat(
                    message=tc.question,
                    bot_id=dataset.metadata.bot_id or None,
                    knowledge_base_id=None,
                )
                results.append(cr)
            except Exception as e:
                logger.error("API call failed for case %s: %s", tc.id, e)
                # Return empty result on failure
                results.append(
                    ChatResult(
                        answer="",
                        conversation_id="",
                        tool_calls=[],
                        sources=[],
                        usage=None,
                        latency_ms=0,
                    )
                )
        return results

    def _extract_failed_cases(self, summary: DatasetEvalSummary) -> list[FailedCase]:
        """Extract failed cases for the mutator."""
        failed = []
        for cr in summary.case_results:
            failed_assertions = [
                ar.assertion_type for ar in cr.assertion_results if not ar.passed
            ]
            if failed_assertions:
                failed.append(
                    FailedCase(
                        case_id=cr.case_id,
                        question=cr.question,
                        actual_answer=cr.answer_snippet,
                        failed_assertions=failed_assertions,
                    )
                )
        return failed

    def _extract_cost_stats(
        self, summary: DatasetEvalSummary, dataset: Dataset
    ) -> CostStats:
        """Extract cost stats for the mutator."""
        return CostStats(
            avg_input_tokens=summary.avg_total_tokens // 2
            if summary.avg_total_tokens
            else 0,
            avg_output_tokens=summary.avg_total_tokens // 2
            if summary.avg_total_tokens
            else 0,
            avg_cost=summary.avg_cost_per_call,
            token_budget=dataset.metadata.cost_config.token_budget,
        )
