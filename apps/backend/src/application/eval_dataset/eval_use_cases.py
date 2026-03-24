"""Single eval + cost estimate use cases."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.shared.exceptions import EntityNotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunEvalCommand:
    tenant_id: str
    dataset_id: str
    api_token: str


class RunSingleEvalUseCase:
    """Run one eval cycle: eval current prompt against a dataset (no mutation)."""

    def __init__(
        self,
        eval_dataset_repository: EvalDatasetRepository,
        api_base_url: str = "http://localhost:8001",
    ) -> None:
        self._dataset_repo = eval_dataset_repository
        self._api_base_url = api_base_url

    async def execute(self, command: RunEvalCommand) -> dict:
        from prompt_optimizer.api_client import AgentAPIClient, ChatResult
        from prompt_optimizer.dataset import (
            Assertion,
            CostConfigData,
            Dataset as CLIDataset,
            DatasetMetadata,
            TestCase,
        )
        from prompt_optimizer.evaluator import Evaluator

        dataset = await self._dataset_repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)

        # Build CLI-compatible dataset
        test_cases = tuple(
            TestCase(
                id=tc.case_id,
                question=tc.question,
                priority=tc.priority,
                category=tc.category,
                assertions=tuple(
                    Assertion(type=a["type"], params=a.get("params", {}))
                    for a in tc.assertions
                ),
                conversation_history=tuple(tc.conversation_history),
            )
            for tc in dataset.test_cases
        )

        cost_cfg = dataset.cost_config or {}
        cli_dataset = CLIDataset(
            metadata=DatasetMetadata(
                tenant_id=command.tenant_id,
                bot_id=dataset.bot_id or "",
                target_prompt=dataset.target_prompt,
                agent_mode=dataset.agent_mode,
                description=dataset.description,
                cost_config=CostConfigData(
                    token_budget=cost_cfg.get("token_budget", 2000),
                    quality_weight=cost_cfg.get("quality_weight", 0.85),
                    cost_weight=cost_cfg.get("cost_weight", 0.15),
                ),
            ),
            test_cases=test_cases,
            default_assertions=tuple(
                Assertion(type=a["type"], params=a.get("params", {}))
                for a in (dataset.default_assertions or [])
            ),
        )

        # Run eval via API
        api_client = AgentAPIClient(
            base_url=self._api_base_url,
            jwt_token=command.api_token,
        )

        try:
            results: list[ChatResult] = []
            for tc in cli_dataset.test_cases:
                try:
                    cr = await api_client.chat(
                        message=tc.question,
                        bot_id=cli_dataset.metadata.bot_id or None,
                    )
                    results.append(cr)
                except Exception as e:
                    logger.error("Eval API call failed for %s: %s", tc.id, e)
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

            evaluator = Evaluator()
            summary = evaluator.evaluate(cli_dataset, results)

            return {
                "dataset_id": command.dataset_id,
                "dataset_name": dataset.name,
                "quality_score": summary.quality_score,
                "cost_score": summary.cost_score,
                "final_score": summary.final_score,
                "avg_total_tokens": summary.avg_total_tokens,
                "avg_cost_per_call": summary.avg_cost_per_call,
                "total_run_cost": summary.total_run_cost,
                "total_cases": len(summary.case_results),
                "passed_cases": sum(
                    1 for cr in summary.case_results if cr.score >= 1.0
                ),
                "p0_failures": summary.p0_failures,
                "case_results": [
                    {
                        "case_id": cr.case_id,
                        "question": cr.question,
                        "priority": cr.priority,
                        "category": cr.category,
                        "score": cr.score,
                        "passed_count": cr.passed_count,
                        "total_count": cr.total_count,
                        "p0_failed": cr.p0_failed,
                        "answer_snippet": cr.answer_snippet,
                        "assertion_results": [
                            {
                                "assertion_type": ar.assertion_type,
                                "passed": ar.passed,
                                "message": ar.message,
                            }
                            for ar in cr.assertion_results
                        ],
                    }
                    for cr in summary.case_results
                ],
            }
        finally:
            await api_client.close()


@dataclass(frozen=True)
class EstimateCostCommand:
    dataset_id: str
    bot_id: str = ""
    model_id: str = ""
    mutator_model_id: str = ""
    max_iterations: int = 20
    patience: int = 5
    budget: int = 200


# Fallback cost per call if model not found in registry
DEFAULT_COST_PER_CALL = 0.01


def _get_model_pricing(model_id: str) -> dict[str, float]:
    """Look up model pricing from DEFAULT_MODELS registry.

    Exact match first, then longest prefix match to avoid
    'gpt-5' matching before 'gpt-5-nano'.
    """
    from src.domain.platform.model_registry import DEFAULT_MODELS

    if not model_id:
        return {}

    # Collect all models
    all_models = []
    for provider_models in DEFAULT_MODELS.values():
        for m in provider_models.get("llm", []):
            all_models.append(m)

    # Exact match first
    for m in all_models:
        if m["model_id"] == model_id:
            return {"input": m.get("input_price", 0.0), "output": m.get("output_price", 0.0)}

    # Longest prefix match (sort by model_id length descending)
    for m in sorted(all_models, key=lambda x: len(x["model_id"]), reverse=True):
        if model_id.startswith(m["model_id"]):
            return {"input": m.get("input_price", 0.0), "output": m.get("output_price", 0.0)}

    return {}


def _estimate_call_cost(
    model_id: str, avg_input_tokens: int = 1500, avg_output_tokens: int = 400
) -> float:
    """Estimate cost for a single API call based on model pricing."""
    pricing = _get_model_pricing(model_id)
    if not pricing:
        return DEFAULT_COST_PER_CALL
    return (
        avg_input_tokens * pricing["input"] / 1_000_000
        + avg_output_tokens * pricing["output"] / 1_000_000
    )


# zh-TW mixed content: 中文 ~1.5 chars/token, 英文 ~4 chars/token
# RAG chunks are mostly Chinese → use 1.8 as weighted average
CHARS_PER_TOKEN = 1.8
DEFAULT_AVG_CHUNK_CHARS = 500
DEFAULT_OUTPUT_TOKENS = 400


class EstimateCostUseCase:
    """Estimate optimization cost based on bot prompt + RAG context + model pricing."""

    def __init__(
        self,
        eval_dataset_repository: EvalDatasetRepository,
        bot_repository=None,
        system_prompt_config_repository=None,
        get_avg_chunk_size=None,
    ) -> None:
        self._dataset_repo = eval_dataset_repository
        self._bot_repo = bot_repository
        self._prompt_config_repo = system_prompt_config_repository
        self._get_avg_chunk_size = get_avg_chunk_size  # callable(tenant_id) -> int

    async def execute(self, command: EstimateCostCommand) -> dict:
        dataset = await self._dataset_repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)

        num_cases = len(dataset.test_cases)

        # --- Token Breakdown ---
        token_breakdown = await self._calculate_token_breakdown(
            command.bot_id, dataset
        )

        # --- Model Pricing ---
        eval_model = command.model_id
        mutator_model = command.mutator_model_id or eval_model
        eval_pricing = _get_model_pricing(eval_model)
        mutator_pricing = _get_model_pricing(mutator_model)

        # Per-call costs using real token estimates
        avg_input = token_breakdown["weighted_avg_input"]
        eval_cost_per_call = _estimate_call_cost(
            eval_model, avg_input_tokens=avg_input, avg_output_tokens=DEFAULT_OUTPUT_TOKENS
        )
        mutator_cost_per_call = _estimate_call_cost(
            mutator_model, avg_input_tokens=avg_input + 500, avg_output_tokens=800
        )

        # --- Cost Calculation ---
        calls_per_iteration = num_cases
        cost_per_iteration = num_cases * eval_cost_per_call + mutator_cost_per_call
        baseline_cost = num_cases * eval_cost_per_call

        min_iterations = min(command.patience, command.max_iterations)
        min_cost = baseline_cost + min_iterations * cost_per_iteration

        max_iterations = min(
            command.max_iterations,
            (command.budget - num_cases) // calls_per_iteration
            if calls_per_iteration > 0 else 0,
        )
        max_total_calls = min(
            num_cases + max_iterations * calls_per_iteration, command.budget
        )
        max_cost = baseline_cost + max_iterations * cost_per_iteration

        return {
            "dataset_id": command.dataset_id,
            "dataset_name": dataset.name,
            "num_cases": num_cases,
            "max_iterations": command.max_iterations,
            "patience": command.patience,
            "budget": command.budget,
            "model_id": eval_model,
            "mutator_model_id": mutator_model,
            "eval_cost_per_call": round(eval_cost_per_call, 6),
            "mutator_cost_per_call": round(mutator_cost_per_call, 6),
            "eval_model_pricing": {
                "input_per_1m": eval_pricing.get("input", 0),
                "output_per_1m": eval_pricing.get("output", 0),
            } if eval_pricing else None,
            "mutator_model_pricing": {
                "input_per_1m": mutator_pricing.get("input", 0),
                "output_per_1m": mutator_pricing.get("output", 0),
            } if mutator_pricing else None,
            "token_breakdown": token_breakdown,
            "calls_per_iteration": calls_per_iteration,
            "baseline_cost": round(baseline_cost, 4),
            "cost_per_iteration": round(cost_per_iteration, 4),
            "min_estimate": {
                "iterations": min_iterations,
                "total_calls": num_cases + min_iterations * calls_per_iteration,
                "cost": round(min_cost, 4),
            },
            "max_estimate": {
                "iterations": max_iterations,
                "total_calls": max_total_calls,
                "cost": round(max_cost, 4),
            },
        }

    async def _calculate_token_breakdown(
        self, bot_id: str, dataset
    ) -> dict:
        """Calculate input token breakdown from bot prompts + RAG + dataset."""
        prompt_tokens = 0
        rag_context_tokens = 0
        rag_top_k = 5
        avg_chunk_chars = DEFAULT_AVG_CHUNK_CHARS
        bot_agent_mode = "router"

        # 1. Prompt tokens + RAG config from bot + system config
        tenant_id = ""
        if bot_id and self._bot_repo:
            try:
                bot = await self._bot_repo.find_by_id(bot_id)
                if bot:
                    bot_agent_mode = bot.agent_mode
                    rag_top_k = bot.llm_params.rag_top_k if hasattr(bot, "llm_params") else 5
                    tenant_id = bot.tenant_id

                    # Bot-level prompt chars
                    bot_prompt_chars = len(bot.system_prompt or "")

                    # System-level prompt chars
                    sys_chars = 0
                    if self._prompt_config_repo:
                        sys_config = await self._prompt_config_repo.get()
                        sys_chars = len(sys_config.base_prompt or "")
                        if bot_agent_mode == "router":
                            sys_chars += len(sys_config.router_mode_prompt or "")
                        elif bot_agent_mode == "react":
                            sys_chars += len(sys_config.react_mode_prompt or "")

                    prompt_tokens = int((bot_prompt_chars + sys_chars) / CHARS_PER_TOKEN)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to calculate prompt tokens: %s", e)
                prompt_tokens = 500  # fallback

        if prompt_tokens == 0:
            prompt_tokens = 500  # fallback

        # 2. RAG context tokens — query real avg chunk size from DB
        if tenant_id and self._get_avg_chunk_size:
            try:
                real_avg = await self._get_avg_chunk_size(tenant_id)
                if real_avg and real_avg > 0:
                    avg_chunk_chars = real_avg
            except Exception:
                pass  # use default

        rag_context_tokens = int(rag_top_k * avg_chunk_chars / CHARS_PER_TOKEN)

        # 3. Avg question tokens from dataset
        total_question_chars = sum(
            len(tc.question) for tc in dataset.test_cases
        )
        avg_question_tokens = int(
            total_question_chars / CHARS_PER_TOKEN / max(len(dataset.test_cases), 1)
        )

        # 4. Avg history tokens
        history_chars = 0
        history_case_count = 0
        for tc in dataset.test_cases:
            if tc.conversation_history:
                history_case_count += 1
                for msg in tc.conversation_history:
                    content = msg.get("content", "") if isinstance(msg, dict) else ""
                    history_chars += len(content)
        avg_history_tokens = int(
            history_chars / CHARS_PER_TOKEN / max(history_case_count, 1)
        ) if history_case_count else 0

        # 5. Classify cases: RAG vs non-RAG
        rag_case_count = 0
        no_rag_case_count = 0
        for tc in dataset.test_cases:
            has_rag_call = False
            has_no_rag = False
            for a in tc.assertions:
                a_type = a.type if hasattr(a, "type") else a.get("type", "")
                a_params = a.params if hasattr(a, "params") else a.get("params", {})
                if a_type == "tool_was_called" and a_params.get("tool_name") == "rag_query":
                    has_rag_call = True
                if a_type == "tool_not_called" and a_params.get("tool_name") == "rag_query":
                    has_no_rag = True
            if has_rag_call:
                rag_case_count += 1
            elif has_no_rag:
                no_rag_case_count += 1
            else:
                rag_case_count += 1  # conservative: assume RAG

        total = max(rag_case_count + no_rag_case_count, 1)
        rag_ratio = rag_case_count / total

        # Weighted average input tokens
        base_input = prompt_tokens + avg_question_tokens + avg_history_tokens
        input_with_rag = base_input + rag_context_tokens
        input_without_rag = base_input
        weighted_avg_input = int(
            input_with_rag * rag_ratio + input_without_rag * (1 - rag_ratio)
        )

        return {
            "prompt_tokens": prompt_tokens,
            "rag_context_tokens": rag_context_tokens,
            "rag_top_k": rag_top_k,
            "avg_chunk_chars": avg_chunk_chars,
            "avg_question_tokens": avg_question_tokens,
            "avg_history_tokens": avg_history_tokens,
            "input_with_rag": input_with_rag,
            "input_without_rag": input_without_rag,
            "weighted_avg_input": weighted_avg_input,
            "output_tokens": DEFAULT_OUTPUT_TOKENS,
            "rag_case_count": rag_case_count,
            "no_rag_case_count": no_rag_case_count,
            "rag_case_ratio": round(rag_ratio, 2),
        }


@dataclass(frozen=True)
class RunValidationCommand:
    tenant_id: str
    dataset_id: str
    api_token: str
    repeats: int = 5
    bot_id: str = ""


class RunValidationEvalUseCase:
    """Validation eval: run N times → per-case pass rate → PASS/FAIL verdict."""

    def __init__(
        self,
        eval_dataset_repository: EvalDatasetRepository,
        optimization_run_repository=None,
        api_base_url: str = "http://localhost:8001",
    ) -> None:
        self._dataset_repo = eval_dataset_repository
        self._run_repo = optimization_run_repository
        self._api_base_url = api_base_url

    async def execute(self, command: RunValidationCommand) -> dict:
        from prompt_optimizer.api_client import AgentAPIClient, ChatResult
        from prompt_optimizer.dataset import (
            Assertion,
            CostConfigData,
            Dataset as CLIDataset,
            DatasetMetadata,
            TestCase,
        )
        from prompt_optimizer.evaluator import Evaluator
        from prompt_optimizer.validation_evaluator import ValidationEvaluator

        dataset = await self._dataset_repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)

        # bot_id: command override > dataset default
        effective_bot_id = command.bot_id or dataset.bot_id or ""

        # Build CLI-compatible dataset
        test_cases = tuple(
            TestCase(
                id=tc.case_id,
                question=tc.question,
                priority=tc.priority,
                category=tc.category,
                assertions=tuple(
                    Assertion(type=a["type"], params=a.get("params", {}))
                    for a in tc.assertions
                ),
                conversation_history=tuple(tc.conversation_history),
            )
            for tc in dataset.test_cases
        )

        cost_cfg = dataset.cost_config or {}
        cli_dataset = CLIDataset(
            metadata=DatasetMetadata(
                tenant_id=command.tenant_id,
                bot_id=effective_bot_id,
                target_prompt=dataset.target_prompt,
                agent_mode=dataset.agent_mode,
                description=dataset.description,
                cost_config=CostConfigData(
                    token_budget=cost_cfg.get("token_budget", 2000),
                    quality_weight=cost_cfg.get("quality_weight", 0.85),
                    cost_weight=cost_cfg.get("cost_weight", 0.15),
                ),
            ),
            test_cases=test_cases,
            default_assertions=tuple(
                Assertion(type=a["type"], params=a.get("params", {}))
                for a in (dataset.default_assertions or [])
            ),
        )

        api_client = AgentAPIClient(
            base_url=self._api_base_url,
            jwt_token=command.api_token,
        )

        async def _eval_fn() -> list[ChatResult]:
            results: list[ChatResult] = []
            for tc in cli_dataset.test_cases:
                try:
                    cr = await api_client.chat(
                        message=tc.question,
                        bot_id=cli_dataset.metadata.bot_id or None,
                    )
                    results.append(cr)
                except Exception as e:
                    logger.error("Validation API call failed for %s: %s", tc.id, e)
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

        try:
            validator = ValidationEvaluator(evaluator=Evaluator())
            summary = await validator.validate(
                cli_dataset, _eval_fn, n_repeats=command.repeats
            )

            # Save to history
            import uuid
            from datetime import datetime, timezone

            run_id = str(uuid.uuid4())
            if self._run_repo:
                from src.domain.eval_dataset.run_entity import OptimizationIteration

                overall_pass_rate = (
                    summary.passed_cases / summary.total_cases
                    if summary.total_cases > 0
                    else 0.0
                )
                iteration = OptimizationIteration(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    iteration=0,
                    tenant_id=command.tenant_id,
                    target_field=dataset.target_prompt,
                    bot_id=effective_bot_id or None,
                    prompt_snapshot="",
                    score=overall_pass_rate,
                    passed_count=summary.passed_cases,
                    total_count=summary.total_cases,
                    is_best=True,
                    details={
                        "type": "validation",
                        "repeats": summary.num_repeats,
                        "verdict": summary.verdict,
                        "unstable_cases": summary.unstable_cases,
                        "p0_failures": summary.p0_failures,
                        "dataset_id": command.dataset_id,
                        "dataset_name": dataset.name,
                    },
                    created_at=datetime.now(timezone.utc),
                )
                try:
                    await self._run_repo.save_iteration(iteration)
                except Exception as e:
                    logger.warning("Failed to save validation history: %s", e)

            return {
                "run_id": run_id,
                "dataset_id": command.dataset_id,
                "dataset_name": dataset.name,
                "verdict": summary.verdict,
                "num_repeats": summary.num_repeats,
                "total_cases": summary.total_cases,
                "passed_cases": summary.passed_cases,
                "failed_cases": summary.failed_cases,
                "unstable_cases": summary.unstable_cases,
                "p0_failures": summary.p0_failures,
                "case_results": [
                    {
                        "case_id": cr.case_id,
                        "question": cr.question,
                        "priority": cr.priority,
                        "pass_rate": cr.pass_rate,
                        "threshold": cr.threshold,
                        "passed": cr.passed,
                        "unstable": cr.unstable,
                        "run_scores": cr.run_scores,
                    }
                    for cr in summary.case_results
                ],
            }
        finally:
            await api_client.close()
