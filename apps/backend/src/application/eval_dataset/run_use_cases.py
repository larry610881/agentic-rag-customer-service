"""Optimization run use cases."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from src.application.eval_dataset._tenant_guard import ensure_dataset_read
from src.domain.bot.repository import BotRepository
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.eval_dataset.run_repository import OptimizationRunRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.prompt_optimizer.run_manager import (
    RunManager,
    RunProgress,
)

logger = logging.getLogger(__name__)


class _ShadowAPIClient:
    """Issue #54 Phase D — 優化迴圈的影子執行包裝：
    每次受測對話自動帶 config_override（記憶體候選 prompt）+ test_mode，
    線上 bots 表全程不被觸碰（spec §6.1，修「候選 prompt 污染線上」破口）。"""

    def __init__(self, inner, target_field: str, prompt_store: dict):
        self._inner = inner
        self._field = target_field
        self._store = prompt_store

    async def chat(self, message, bot_id=None, **kwargs):
        candidate = self._store.get(self._field)
        override = {self._field: candidate} if candidate is not None else None
        return await self._inner.chat(
            message=message,
            bot_id=bot_id,
            config_override=override,
            test_mode=True,
            **kwargs,
        )

    async def close(self):
        await self._inner.close()


@dataclass(frozen=True)
class StartRunCommand:
    tenant_id: str
    dataset_id: str
    api_token: str
    refresh_token: str = ""
    max_iterations: int = 20
    patience: int = 5
    budget: int = 200
    dry_run: bool = False
    role: str | None = None


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
        record_usage_factory=None,
        create_version_factory=None,
    ) -> None:
        self._dataset_repo = eval_dataset_repository
        self._run_manager = run_manager
        self._db_url = db_url
        self._api_base_url = api_base_url
        self._provider_repo = provider_setting_repository
        self._encryption = encryption_service
        # Issue #54 Phase B — mutator 記帳用。傳 provider callable（.provider
        # delegation 模式）：背景任務在 independent_session_scope 內 resolve，
        # 讓 use case 綁到新 session 而非已關閉的 request session。
        self._record_usage_factory = record_usage_factory
        # Issue #54 Phase D — 優化產出建 draft 版本用（同 .provider 模式）
        self._create_version_factory = create_version_factory

    async def execute(self, command: StartRunCommand) -> str:
        """Start an optimization run. Returns run_id."""
        dataset = await self._dataset_repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)
        # C7：跨租戶對他人題集啟動 run 會把題集 snapshot 寫進可見 iterations → 404
        ensure_dataset_read(dataset, command.tenant_id, command.role)

        # Snapshot dataset data before spawning background task
        dataset_snapshot = {
            "name": dataset.name,
            "description": dataset.description,
            "bot_id": dataset.bot_id,
            "target_prompt": dataset.target_prompt,
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

    async def _create_optimizer_draft(
        self,
        *,
        tenant_id: str,
        bot_id: str | None,
        target_field: str,
        best_prompt: str,
        initial_prompt: str,
        improved: bool,
        run_id: str,
    ) -> str | None:
        """優化產出 → 版本狀態機（spec §6.2）。fail-open：建版失敗只 warn。
        回傳 version_id 或 None（未進步 / 不適用 / 失敗）。"""
        if (
            self._create_version_factory is None
            or not bot_id
            or not improved
            or not best_prompt
            or best_prompt == initial_prompt
        ):
            return None
        try:
            from src.application.prompt_gate.version_use_cases import (
                CreateConfigVersionCommand,
            )
            from src.domain.prompt_gate.config_snapshot import SNAPSHOT_FIELDS
            from src.domain.prompt_gate.entity import SOURCE_OPTIMIZER
            from src.infrastructure.db.session_middleware import (
                independent_session_scope,
            )

            if target_field not in SNAPSHOT_FIELDS:
                logger.info(
                    "optimizer draft skipped: target_field=%s 不在版控白名單",
                    target_field,
                )
                return None
            async with independent_session_scope():
                create_version = self._create_version_factory()
                version = await create_version.execute(
                    CreateConfigVersionCommand(
                        tenant_id=tenant_id,
                        bot_id=bot_id,
                        changes={target_field: best_prompt},
                        source=SOURCE_OPTIMIZER,
                        source_run_id=run_id,
                    )
                )
            logger.info(
                "optimizer draft created: run=%s version=%s",
                run_id, version.id,
            )
            return str(version.id)
        except Exception:
            logger.warning(
                "optimizer draft creation failed (fail-open) run=%s",
                run_id, exc_info=True,
            )
            return None

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
            DatasetMetadata,
            TestCase,
        )
        from prompt_optimizer.dataset import (
            Dataset as CLIDataset,
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
                    agent_mode="react",
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
                refresh_token=command.refresh_token,
                usage_category="prompt_optimize",
                run_id=run_id,
            )

            # Use sync RunHistoryClient for DB persistence (its own connection)
            history_client = (
                RunHistoryClient(self._db_url) if self._db_url else None
            )

            # Pre-load actual prompt from DB via sync client
            from prompt_optimizer.db_client import PromptDBClient

            prompt_store: dict[str, str] = {}
            prompt_db: PromptDBClient | None = None
            if self._db_url:
                try:
                    prompt_db = PromptDBClient(db_url=self._db_url)
                    initial_prompt = prompt_db.read_prompt(target)
                    prompt_store[target.field] = initial_prompt
                except Exception as e:
                    logger.warning("Failed to pre-load prompt: %s", e)

            # Issue #54 Phase D — 收尾比對用：prompt_store 會被迴圈改寫，
            # baseline 要在這裡先固定下來
            baseline_prompt = prompt_store.get(ds["target_prompt"], "")

            def read_prompt(t: PromptTarget) -> str:
                return prompt_store.get(t.field, "")

            def write_prompt(t: PromptTarget, prompt: str) -> None:
                # Issue #54 Phase D — 候選 prompt 只存記憶體；受測對話由
                # _ShadowAPIClient 以 config_override 帶入，全程不寫線上表
                prompt_store[t.field] = prompt

            from prompt_optimizer.mutator import PromptMutator

            # Issue #54 Phase B — mutator LLM 用量落帳（prompt_optimize 分類，
            # fail-open：記帳失敗只 warn 不影響優化迴圈）
            bot_id_for_usage = ds.get("bot_id") or None

            async def _record_mutator_usage(
                model_name: str, usage_meta: dict
            ) -> None:
                if self._record_usage_factory is None:
                    return
                try:
                    from src.domain.rag.value_objects import TokenUsage
                    from src.infrastructure.db.session_middleware import (
                        independent_session_scope,
                    )

                    usage = TokenUsage(
                        model=model_name,
                        input_tokens=int(usage_meta.get("input_tokens", 0)),
                        output_tokens=int(usage_meta.get("output_tokens", 0)),
                        estimated_cost=0.0,  # RecordUsage 會依 registry 估價
                    )
                    async with independent_session_scope():
                        record_usage = self._record_usage_factory()
                        await record_usage.execute(
                            tenant_id=command.tenant_id,
                            request_type="prompt_optimize",
                            usage=usage,
                            bot_id=bot_id_for_usage,
                            run_id=run_id,
                        )
                except Exception:
                    logger.warning(
                        "mutator usage recording failed (fail-open)",
                        exc_info=True,
                    )

            mutator = (
                PromptMutator(
                    api_key=mutator_api_key,
                    on_usage=_record_mutator_usage,
                )
                if mutator_api_key
                else None
            )

            runner = KarpathyLoopRunner(
                api_client=_ShadowAPIClient(  # type: ignore[arg-type]  # duck-type 相容
                    api_client,
                    target_field=ds["target_prompt"],
                    prompt_store=prompt_store,
                ),
                db_read_prompt=read_prompt,
                db_write_prompt=write_prompt,
                evaluator=Evaluator(),
                mutator=mutator,
                use_history_override=True,
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
            from prompt_optimizer.runner import IterationResult, ProgressEvent

            async def _on_progress(evt: ProgressEvent) -> None:
                self._run_manager.update_run(
                    run_id,
                    current_iteration=evt.iteration,
                    current_score=evt.score if evt.score > 0 else None,
                    baseline_score=evt.baseline_score if evt.baseline_score > 0 else None,
                    best_score=evt.best_score if evt.best_score > 0 else None,
                    progress_message=evt.message,
                )
                # Append to score_log on iteration completion
                if evt.phase == "iteration_done":
                    active = self._run_manager.get_run(run_id)
                    if active:
                        active.score_log.append(
                            {"iteration": evt.iteration, "score": evt.score}
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

            # Iteration callback: save each iteration to DB immediately
            def _on_iteration(it: IterationResult) -> None:
                if not history_client:
                    return
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
                                        "passed": ar.passed,
                                        "assertion_type": ar.assertion_type,
                                        "message": ar.message,
                                    }
                                    for ar in cr.assertion_results
                                ],
                            }
                            for cr in it.eval_summary.case_results
                        ],
                    },
                )

            # Run the optimization loop
            result = await runner.run(
                config, cli_dataset, run_id=run_id,
                on_progress=_on_progress,
                on_iteration=_on_iteration,
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

            # Issue #54 Phase D — 產出走版本狀態機：有進步才建 draft
            version_id = await self._create_optimizer_draft(
                tenant_id=command.tenant_id,
                bot_id=ds.get("bot_id") or None,
                target_field=ds["target_prompt"],
                best_prompt=result.best_prompt,
                initial_prompt=baseline_prompt,
                improved=result.best_score > result.baseline_score,
                run_id=run_id,
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
                    version_id=version_id,
                    message=(
                        f"Optimization complete: "
                        f"{result.baseline_score:.4f} → {result.best_score:.4f}"
                        + (
                            f"；已建立版本 draft（{version_id[:8]}），"
                            "請前往驗證/發布"
                            if version_id
                            else ""
                        )
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
            if prompt_db:
                prompt_db.close()


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

    async def execute(
        self, run_id: str, tenant_id: str | None = None
    ) -> dict:
        """Get run detail with iterations（tenant_id=None → system_admin）。"""
        iterations = await self._run_repo.get_iterations(run_id)
        active = self._run_manager.get_run(run_id)
        _check_run_tenant(iterations, tenant_id)
        if (
            tenant_id is not None
            and active is not None
            and active.tenant_id != tenant_id
        ):
            raise EntityNotFoundError("OptimizationRun", run_id)

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
            "current_score": active.current_score if active else None,
            "stopped_reason": active.stopped_reason if active else "",
            "current_iteration": (
                active.current_iteration
                if active
                else (iterations[-1].iteration if iterations else 0)
            ),
            "max_iterations": (
                active.max_iterations
                if active
                else (iterations[-1].iteration if iterations else 0)
            ),
            "total_api_calls": active.total_api_calls if active else 0,
            "started_at": (
                active.started_at.isoformat()
                if active
                else (
                    iterations[0].created_at.isoformat() if iterations else ""
                )
            ),
            "progress_message": active.progress_message if active else "",
            "progress_log": active.progress_log if active else [],
            "score_log": active.score_log if active else [],
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

    async def execute(
        self, run_id: str, tenant_id: str | None = None
    ) -> bool:
        active = self._run_manager.get_run(run_id)
        if (
            tenant_id is not None
            and active is not None
            and active.tenant_id != tenant_id
        ):
            raise EntityNotFoundError("ActiveRun", run_id)
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


# Issue #54 Phase D — 系統級 prompt 的 setattr 白名單（修無白名單 setattr 破口）
_SYSTEM_PROMPT_FIELDS = frozenset({"system_prompt"})


def _check_run_tenant(iterations: list, tenant_id: str | None) -> None:
    """Run 端點 tenant scoping（事實校正 #9）：None = system_admin 免檢。"""
    if tenant_id is None or not iterations:
        return
    if iterations[0].tenant_id != tenant_id:
        raise EntityNotFoundError("OptimizationRun", "run")


class RollbackRunUseCase:
    """Issue #54 Phase D — rollback 收斂到版本狀態機（spec §6.4）：
    bot 級 = 建 optimizer 版本 → 嘗試發布（gate 啟用時停在 draft，回報導引）；
    system 級 = 白名單 setattr（system prompt 無版本化，v1 保留舊路徑）。"""

    def __init__(
        self,
        optimization_run_repository: OptimizationRunRepository,
        bot_repository: BotRepository,
        system_prompt_config_repository=None,
        create_version_use_case=None,
        publish_version_use_case=None,
    ) -> None:
        self._run_repo = optimization_run_repository
        self._bot_repo = bot_repository
        self._system_prompt_repo = system_prompt_config_repository
        self._create_version = create_version_use_case
        self._publish_version = publish_version_use_case

    async def _rollback_via_version(
        self, target, run_id: str
    ) -> tuple[bool, str | None, bool, str]:
        """建 optimizer 版本 → 嘗試發布。回傳 (applied, version_id, published, note)。"""
        from src.application.prompt_gate.version_use_cases import (
            CreateConfigVersionCommand,
        )
        from src.domain.prompt_gate.entity import (
            SOURCE_OPTIMIZER,
            GateBlockedError,
        )
        from src.domain.shared.exceptions import ValidationError

        version_id: str | None = None
        note = ""
        try:
            version = await self._create_version.execute(
                CreateConfigVersionCommand(
                    tenant_id=target.tenant_id,
                    bot_id=target.bot_id,
                    changes={target.target_field: target.prompt_snapshot},
                    source=SOURCE_OPTIMIZER,
                    source_run_id=run_id,
                )
            )
            version_id = version.id
        except ValidationError as exc:
            return False, None, False, str(exc)  # no_changes 等
        if self._publish_version is not None:
            try:
                await self._publish_version.execute(
                    target.tenant_id, version_id
                )
                return True, version_id, True, ""
            except GateBlockedError as exc:
                note = f"已建立 draft，發布被閘門攔下：{exc}"
        return True, version_id, False, note

    async def execute(
        self,
        run_id: str,
        target_iteration: int,
        tenant_id: str | None = None,
    ) -> dict:
        """Apply a specific iteration's prompt via the version state machine."""
        iterations = await self._run_repo.get_iterations(run_id)
        if not iterations:
            raise EntityNotFoundError("OptimizationRun", run_id)
        _check_run_tenant(iterations, tenant_id)

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

        applied = False
        version_id: str | None = None
        published = False
        note = ""

        # Bot-level prompt → 版本狀態機（唯一寫入通道）
        if target.bot_id and self._create_version is not None:
            applied, version_id, published, note = (
                await self._rollback_via_version(target, run_id)
            )

        # System-level prompt（無版本化，白名單 setattr）
        if not target.bot_id and self._system_prompt_repo:
            if target.target_field not in _SYSTEM_PROMPT_FIELDS:
                raise EntityNotFoundError(
                    "SystemPromptField", target.target_field
                )
            config = await self._system_prompt_repo.get()
            setattr(config, target.target_field, target.prompt_snapshot)
            await self._system_prompt_repo.save(config)
            applied = True
            published = True
            logger.info(
                "Applied iteration %d prompt to system.%s",
                target_iteration, target.target_field,
            )

        return {
            "run_id": run_id,
            "iteration": target_iteration,
            "prompt_snapshot": target.prompt_snapshot,
            "score": target.score,
            "applied": applied,
            "version_id": version_id,
            "published": published,
            "note": note,
        }


class GetRunReportUseCase:
    def __init__(
        self,
        optimization_run_repository: OptimizationRunRepository,
    ) -> None:
        self._run_repo = optimization_run_repository

    async def execute(
        self, run_id: str, tenant_id: str | None = None
    ) -> str:
        """Generate a markdown report for a run."""
        iterations = await self._run_repo.get_iterations(run_id)
        if not iterations:
            raise EntityNotFoundError("OptimizationRun", run_id)
        _check_run_tenant(iterations, tenant_id)

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

    async def execute(
        self, run_id: str, iteration: int, tenant_id: str | None = None
    ) -> dict:
        """Get the prompt diff between baseline and a specific iteration."""
        iterations = await self._run_repo.get_iterations(run_id)
        if not iterations:
            raise EntityNotFoundError("OptimizationRun", run_id)
        _check_run_tenant(iterations, tenant_id)

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
