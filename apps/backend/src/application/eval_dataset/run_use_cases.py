"""Optimization run use cases."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from src.domain.bot.repository import BotRepository
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.eval_dataset.run_repository import OptimizationRunRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.prompt_optimizer.run_manager import (
    RunManager,
    RunProgress,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartRunCommand:
    tenant_id: str
    dataset_id: str
    api_token: str
    max_iterations: int = 20
    patience: int = 5
    budget: int = 200
    dry_run: bool = False


class StartRunUseCase:
    """Start an optimization run as a background task.

    NOTE: The background task must NOT use request-scoped repos/sessions.
    It uses the sync RunHistoryClient for DB persistence and the
    singleton RunManager for progress tracking.
    """

    def __init__(
        self,
        eval_dataset_repository: EvalDatasetRepository,
        run_manager: RunManager,
        db_url: str = "",
        api_base_url: str = "http://localhost:8001",
        provider_setting_repository=None,
        encryption_service=None,
    ) -> None:
        self._dataset_repo = eval_dataset_repository
        self._run_manager = run_manager
        self._db_url = db_url
        self._api_base_url = api_base_url
        self._provider_repo = provider_setting_repository
        self._encryption = encryption_service

    async def execute(self, command: StartRunCommand) -> str:
        """Start an optimization run. Returns run_id."""
        dataset = await self._dataset_repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)

        # Snapshot dataset data before spawning background task
        dataset_snapshot = {
            "name": dataset.name,
            "description": dataset.description,
            "bot_id": dataset.bot_id,
            "target_prompt": dataset.target_prompt,
            "agent_mode": dataset.agent_mode,
            "default_assertions": list(dataset.default_assertions or []),
            "cost_config": dict(dataset.cost_config or {}),
            "test_cases": [
                {
                    "case_id": tc.case_id,
                    "question": tc.question,
                    "priority": tc.priority,
                    "category": tc.category,
                    "assertions": list(tc.assertions),
                    "conversation_history": list(tc.conversation_history),
                }
                for tc in dataset.test_cases
            ],
        }

        # Resolve mutator API key from provider_settings (before background task)
        mutator_api_key = ""
        if self._provider_repo and self._encryption:
            try:
                mutator_api_key = await self._resolve_llm_api_key()
            except Exception as e:
                logger.warning("Failed to resolve mutator API key: %s", e)

        run_id = self._run_manager.create_run(
            tenant_id=command.tenant_id,
            dataset_id=command.dataset_id,
            dataset_name=dataset.name,
            target_field=dataset.target_prompt,
            bot_id=dataset.bot_id,
            max_iterations=command.max_iterations,
        )

        task = asyncio.create_task(
            self._run_optimization(run_id, command, dataset_snapshot, mutator_api_key)
        )
        self._run_manager.set_task(run_id, task)

        return run_id

    async def _resolve_llm_api_key(self) -> str:
        """Resolve LLM API key from the first enabled LLM provider setting."""
        settings = await self._provider_repo.find_all()
        for s in settings:
            if s.provider_type.value == "llm" and s.is_enabled and s.api_key_encrypted:
                return self._encryption.decrypt(s.api_key_encrypted)
        return ""

    async def _run_optimization(
        self, run_id: str, command: StartRunCommand, ds: dict, mutator_api_key: str = ""
    ) -> None:
        """Background task: run the Karpathy optimization loop.

        Uses its own DB connections (sync RunHistoryClient) — never touches
        request-scoped sessions.
        """
        from prompt_optimizer.api_client import AgentAPIClient
        from prompt_optimizer.config import OptimizationConfig, PromptTarget
        from prompt_optimizer.dataset import (
            Assertion,
            CostConfigData,
            Dataset as CLIDataset,
            DatasetMetadata,
            TestCase,
        )
        from prompt_optimizer.evaluator import Evaluator
        from prompt_optimizer.history import RunHistoryClient
        from prompt_optimizer.runner import KarpathyLoopRunner

        history_client = None
        api_client = None

        try:
            # Build CLI-compatible dataset from snapshot
            test_cases = tuple(
                TestCase(
                    id=tc["case_id"],
                    question=tc["question"],
                    priority=tc.get("priority", "P1"),
                    category=tc.get("category", ""),
                    assertions=tuple(
                        Assertion(type=a["type"], params=a.get("params", {}))
                        for a in tc.get("assertions", [])
                    ),
                    conversation_history=tuple(
                        tc.get("conversation_history", [])
                    ),
                )
                for tc in ds["test_cases"]
            )

            cost_cfg = ds.get("cost_config", {})
            cli_dataset = CLIDataset(
                metadata=DatasetMetadata(
                    tenant_id=command.tenant_id,
                    bot_id=ds.get("bot_id") or "",
                    target_prompt=ds["target_prompt"],
                    agent_mode=ds.get("agent_mode", "router"),
                    description=ds.get("description", ""),
                    cost_config=CostConfigData(
                        token_budget=cost_cfg.get("token_budget", 2000),
                        quality_weight=cost_cfg.get("quality_weight", 0.85),
                        cost_weight=cost_cfg.get("cost_weight", 0.15),
                    ),
                ),
                test_cases=test_cases,
                default_assertions=tuple(
                    Assertion(type=a["type"], params=a.get("params", {}))
                    for a in ds.get("default_assertions", [])
                ),
            )

            target = PromptTarget(
                level="bot" if ds.get("bot_id") else "system",
                field=ds["target_prompt"],
                bot_id=ds.get("bot_id"),
                tenant_id=command.tenant_id,
            )

            config = OptimizationConfig(
                api_base_url=self._api_base_url,
                api_token=command.api_token,
                db_url=self._db_url,
                target=target,
                max_iterations=command.max_iterations,
                patience=command.patience,
                budget=command.budget,
                dry_run=command.dry_run,
            )

            api_client = AgentAPIClient(
                base_url=config.api_base_url,
                jwt_token=config.api_token,
            )

            # Use sync RunHistoryClient for DB persistence (its own connection)
            history_client = (
                RunHistoryClient(self._db_url) if self._db_url else None
            )

            # Simple in-memory prompt storage for the runner
            prompt_store: dict[str, str] = {}

            def read_prompt(t: PromptTarget) -> str:
                return prompt_store.get(t.field, "")

            def write_prompt(t: PromptTarget, prompt: str) -> None:
                prompt_store[t.field] = prompt

            from prompt_optimizer.mutator import PromptMutator

            mutator = PromptMutator(api_key=mutator_api_key) if mutator_api_key else None

            runner = KarpathyLoopRunner(
                api_client=api_client,
                db_read_prompt=read_prompt,
                db_write_prompt=write_prompt,
                evaluator=Evaluator(),
                mutator=mutator,
            )

            # Publish started event
            await self._run_manager.publish_progress(
                run_id,
                RunProgress(
                    run_id=run_id,
                    event="started",
                    max_iterations=command.max_iterations,
                    message=f"Starting optimization for '{ds['name']}'",
                ),
            )

            # Progress callback: update RunManager on each case/iteration
            from prompt_optimizer.runner import ProgressEvent

            async def _on_progress(evt: ProgressEvent) -> None:
                self._run_manager.update_run(
                    run_id,
                    current_iteration=evt.iteration,
                    baseline_score=evt.baseline_score if evt.baseline_score > 0 else None,
                    best_score=evt.best_score if evt.best_score > 0 else None,
                    progress_message=evt.message,
                )
                await self._run_manager.publish_progress(
                    run_id,
                    RunProgress(
                        run_id=run_id,
                        event=evt.phase,
                        iteration=evt.iteration,
                        max_iterations=evt.max_iterations,
                        score=evt.score,
                        best_score=evt.best_score,
                        baseline_score=evt.baseline_score,
                        message=evt.message,
                    ),
                )

            result_holder: dict = {"api_calls": 0}

            # Run the optimization loop
            result = await runner.run(
                config, cli_dataset, run_id=run_id, on_progress=_on_progress
            )

            # Save iterations to DB via sync history client
            if history_client:
                for it in result.iterations:
                    history_client.save_iteration(
                        run_id=run_id,
                        iteration=it.iteration,
                        tenant_id=command.tenant_id,
                        target_field=ds["target_prompt"],
                        bot_id=ds.get("bot_id"),
                        prompt_snapshot=it.prompt_snapshot,
                        score=it.eval_summary.final_score,
                        passed_count=sum(
                            1
                            for cr in it.eval_summary.case_results
                            if cr.score >= 1.0
                        ),
                        total_count=len(it.eval_summary.case_results),
                        is_best=it.is_best,
                        details={
                            "quality_score": it.eval_summary.quality_score,
                            "cost_score": it.eval_summary.cost_score,
                            "avg_total_tokens": it.eval_summary.avg_total_tokens,
                            "accepted": it.accepted,
                        },
                    )

            # Publish iteration progress for each
            for it in result.iterations:
                await self._run_manager.publish_progress(
                    run_id,
                    RunProgress(
                        run_id=run_id,
                        event="iteration",
                        iteration=it.iteration,
                        max_iterations=command.max_iterations,
                        score=it.eval_summary.final_score,
                        best_score=result.best_score,
                        baseline_score=result.baseline_score,
                        is_best=it.is_best,
                        accepted=it.accepted,
                        total_api_calls=result.total_api_calls,
                    ),
                )

            # Update run status
            self._run_manager.update_run(
                run_id,
                status="completed",
                baseline_score=result.baseline_score,
                best_score=result.best_score,
                current_iteration=len(result.iterations) - 1,
                total_api_calls=result.total_api_calls,
                stopped_reason=result.stopped_reason,
            )

            await self._run_manager.publish_progress(
                run_id,
                RunProgress(
                    run_id=run_id,
                    event="completed",
                    baseline_score=result.baseline_score,
                    best_score=result.best_score,
                    total_api_calls=result.total_api_calls,
                    stopped_reason=result.stopped_reason,
                    message=(
                        f"Optimization complete: "
                        f"{result.baseline_score:.4f} → {result.best_score:.4f}"
                    ),
                ),
            )

        except Exception as e:
            logger.exception("Optimization run %s failed", run_id)
            self._run_manager.update_run(
                run_id, status="failed", stopped_reason=str(e)
            )
            await self._run_manager.publish_progress(
                run_id,
                RunProgress(run_id=run_id, event="error", message=str(e)),
            )
        finally:
            if api_client:
                await api_client.close()
            if history_client:
                history_client.close()


class ListRunsUseCase:
    def __init__(
        self,
        optimization_run_repository: OptimizationRunRepository,
        run_manager: RunManager,
    ) -> None:
        self._run_repo = optimization_run_repository
        self._run_manager = run_manager

    async def execute(
        self,
        tenant_id: str | None = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """List runs combining active (in-memory) and historical (DB) runs."""
        db_runs = await self._run_repo.list_runs(
            tenant_id, limit=limit, offset=offset
        )
        active_runs = self._run_manager.list_runs(tenant_id)

        # Merge: active runs override DB runs with same run_id
        active_ids = {r.run_id for r in active_runs}
        merged = []

        for ar in active_runs:
            merged.append({
                "run_id": ar.run_id,
                "tenant_id": ar.tenant_id,
                "dataset_id": ar.dataset_id,
                "dataset_name": ar.dataset_name,
                "target_field": ar.target_field,
                "bot_id": ar.bot_id,
                "run_type": "optimization",
                "status": ar.status,
                "baseline_score": ar.baseline_score,
                "best_score": ar.best_score,
                "current_iteration": ar.current_iteration,
                "max_iterations": ar.max_iterations,
                "total_api_calls": ar.total_api_calls,
                "stopped_reason": ar.stopped_reason,
                "started_at": ar.started_at.isoformat(),
                "completed_at": (
                    ar.completed_at.isoformat() if ar.completed_at else None
                ),
            })

        for dr in db_runs:
            if dr["run_id"] not in active_ids:
                started = dr.get("started_at")
                started_str = (
                    started.isoformat()
                    if hasattr(started, "isoformat")
                    else str(started)
                )
                merged.append({
                    "run_id": dr["run_id"],
                    "tenant_id": dr["tenant_id"],
                    "dataset_id": "",
                    "dataset_name": "",
                    "target_field": dr["target_field"],
                    "bot_id": dr.get("bot_id"),
                    "run_type": dr.get("run_type") or "optimization",
                    "status": "completed",
                    "baseline_score": float(dr.get("baseline_score", 0)),
                    "best_score": float(dr.get("best_score", 0)),
                    "current_iteration": dr.get("total_iterations", 0),
                    "max_iterations": dr.get("total_iterations", 0),
                    "total_api_calls": 0,
                    "stopped_reason": "",
                    "started_at": started_str,
                    "completed_at": None,
                })

        return merged[:limit]

    async def count(self, tenant_id: str | None = None) -> int:
        db_count = await self._run_repo.count_runs(tenant_id)
        active_count = len(self._run_manager.list_runs(tenant_id))
        return db_count + active_count


class GetRunUseCase:
    def __init__(
        self,
        optimization_run_repository: OptimizationRunRepository,
        run_manager: RunManager,
    ) -> None:
        self._run_repo = optimization_run_repository
        self._run_manager = run_manager

    async def execute(self, run_id: str) -> dict:
        """Get run detail with iterations."""
        iterations = await self._run_repo.get_iterations(run_id)
        active = self._run_manager.get_run(run_id)

        if not iterations and not active:
            raise EntityNotFoundError("OptimizationRun", run_id)

        status = active.status if active else "completed"
        baseline_score = 0.0
        best_score = 0.0
        tenant_id = ""
        target_field = ""
        bot_id = None

        if iterations:
            baseline_score = iterations[0].score
            best_candidates = [it for it in iterations if it.is_best]
            best_score = (
                max(it.score for it in best_candidates)
                if best_candidates
                else baseline_score
            )
            tenant_id = iterations[0].tenant_id
            target_field = iterations[0].target_field
            bot_id = iterations[0].bot_id

        if active:
            baseline_score = active.baseline_score or baseline_score
            best_score = active.best_score or best_score
            tenant_id = active.tenant_id
            target_field = active.target_field
            bot_id = active.bot_id

        return {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "target_field": target_field,
            "bot_id": bot_id,
            "status": status,
            "baseline_score": baseline_score,
            "best_score": best_score,
            "stopped_reason": active.stopped_reason if active else "",
            "current_iteration": (
                active.current_iteration
                if active
                else (iterations[-1].iteration if iterations else 0)
            ),
            "max_iterations": active.max_iterations if active else 0,
            "total_api_calls": active.total_api_calls if active else 0,
            "started_at": (
                active.started_at.isoformat()
                if active
                else (
                    iterations[0].created_at.isoformat() if iterations else ""
                )
            ),
            "progress_message": active.progress_message if active else "",
            "iterations": [
                {
                    "iteration": it.iteration,
                    "score": it.score,
                    "passed_count": it.passed_count,
                    "total_count": it.total_count,
                    "is_best": it.is_best,
                    "details": it.details,
                    "prompt_snapshot": it.prompt_snapshot,
                    "created_at": it.created_at.isoformat(),
                }
                for it in iterations
            ],
        }


class StopRunUseCase:
    def __init__(self, run_manager: RunManager) -> None:
        self._run_manager = run_manager

    async def execute(self, run_id: str) -> bool:
        success = self._run_manager.request_stop(run_id)
        if not success:
            raise EntityNotFoundError("ActiveRun", run_id)
        self._run_manager.update_run(
            run_id, status="stopped", stopped_reason="user_stopped"
        )
        await self._run_manager.publish_progress(
            run_id,
            RunProgress(
                run_id=run_id,
                event="stopped",
                message="Run stopped by user",
            ),
        )
        return True


class RollbackRunUseCase:
    def __init__(
        self,
        optimization_run_repository: OptimizationRunRepository,
        bot_repository: BotRepository,
    ) -> None:
        self._run_repo = optimization_run_repository
        self._bot_repo = bot_repository

    async def execute(self, run_id: str, target_iteration: int) -> dict:
        """Rollback bot prompt to a specific iteration's prompt."""
        iterations = await self._run_repo.get_iterations(run_id)
        if not iterations:
            raise EntityNotFoundError("OptimizationRun", run_id)

        target = None
        for it in iterations:
            if it.iteration == target_iteration:
                target = it
                break

        if target is None:
            raise EntityNotFoundError(
                "OptimizationIteration",
                f"run={run_id}, iteration={target_iteration}",
            )

        # Apply prompt to bot
        if target.bot_id:
            bot = await self._bot_repo.find_by_id(target.bot_id)
            if bot:
                setattr(bot, target.target_field, target.prompt_snapshot)
                await self._bot_repo.save(bot)

        return {
            "run_id": run_id,
            "iteration": target_iteration,
            "prompt_snapshot": target.prompt_snapshot,
            "score": target.score,
            "applied": True,
        }


class GetRunReportUseCase:
    def __init__(
        self,
        optimization_run_repository: OptimizationRunRepository,
    ) -> None:
        self._run_repo = optimization_run_repository

    async def execute(self, run_id: str) -> str:
        """Generate a markdown report for a run."""
        iterations = await self._run_repo.get_iterations(run_id)
        if not iterations:
            raise EntityNotFoundError("OptimizationRun", run_id)

        baseline = iterations[0]
        best = max(iterations, key=lambda it: it.score)

        lines = [
            "# Optimization Run Report",
            "",
            f"**Run ID:** `{run_id}`",
            f"**Target:** `{baseline.target_field}`",
            f"**Bot:** `{baseline.bot_id or 'system'}`",
            f"**Iterations:** {len(iterations) - 1}",
            "",
            "## Score Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Baseline Score | {baseline.score:.4f} |",
            f"| Best Score | {best.score:.4f} |",
            f"| Improvement | {best.score - baseline.score:+.4f} |",
            f"| Best Iteration | {best.iteration} |",
            "",
            "## Iteration History",
            "",
            "| # | Score | Passed | Total | Best |",
            "|---|-------|--------|-------|------|",
        ]

        for it in iterations:
            best_marker = (
                " **best**" if it.is_best and it.iteration > 0 else ""
            )
            lines.append(
                f"| {it.iteration} | {it.score:.4f} | {it.passed_count} | "
                f"{it.total_count} | {best_marker} |"
            )

        lines.append("")
        return "\n".join(lines)


class GetRunDiffUseCase:
    def __init__(
        self,
        optimization_run_repository: OptimizationRunRepository,
    ) -> None:
        self._run_repo = optimization_run_repository

    async def execute(self, run_id: str, iteration: int) -> dict:
        """Get the prompt diff between baseline and a specific iteration."""
        iterations = await self._run_repo.get_iterations(run_id)
        if not iterations:
            raise EntityNotFoundError("OptimizationRun", run_id)

        baseline = iterations[0]
        target = None
        for it in iterations:
            if it.iteration == iteration:
                target = it
                break

        if target is None:
            raise EntityNotFoundError(
                "OptimizationIteration",
                f"run={run_id}, iteration={iteration}",
            )

        return {
            "run_id": run_id,
            "iteration": iteration,
            "baseline_prompt": baseline.prompt_snapshot,
            "iteration_prompt": target.prompt_snapshot,
            "baseline_score": baseline.score,
            "iteration_score": target.score,
            "is_best": target.is_best,
        }
