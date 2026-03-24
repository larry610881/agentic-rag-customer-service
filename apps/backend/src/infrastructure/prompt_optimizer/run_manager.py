"""Run manager: manages background optimization tasks and SSE progress."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


@dataclass
class RunProgress:
    """Progress event for SSE streaming."""

    run_id: str
    event: str  # "started" | "iteration" | "completed" | "stopped" | "error"
    iteration: int = 0
    max_iterations: int = 0
    score: float = 0.0
    best_score: float = 0.0
    baseline_score: float = 0.0
    is_best: bool = False
    accepted: bool = False
    stopped_reason: str = ""
    total_api_calls: int = 0
    message: str = ""
    timestamp: str = ""

    def to_sse(self) -> str:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        return f"data: {json.dumps(asdict(self))}\n\n"


@dataclass
class ActiveRun:
    """Tracks a running optimization."""

    run_id: str
    tenant_id: str
    dataset_id: str
    dataset_name: str
    target_field: str
    bot_id: str | None
    status: str = "running"  # running | completed | stopped | failed
    baseline_score: float = 0.0
    best_score: float = 0.0
    current_score: float = 0.0
    current_iteration: int = 0
    max_iterations: int = 0
    total_api_calls: int = 0
    stopped_reason: str = ""
    progress_message: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    task: asyncio.Task | None = field(default=None, repr=False)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    progress_queue: asyncio.Queue = field(
        default_factory=lambda: asyncio.Queue(maxsize=100), repr=False
    )


class RunManager:
    """Singleton service managing active optimization runs."""

    def __init__(self) -> None:
        self._runs: dict[str, ActiveRun] = {}

    def create_run(
        self,
        tenant_id: str,
        dataset_id: str,
        dataset_name: str,
        target_field: str,
        bot_id: str | None,
        max_iterations: int,
    ) -> str:
        run_id = str(uuid.uuid4())
        run = ActiveRun(
            run_id=run_id,
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            target_field=target_field,
            bot_id=bot_id,
            max_iterations=max_iterations,
        )
        self._runs[run_id] = run
        return run_id

    def get_run(self, run_id: str) -> ActiveRun | None:
        return self._runs.get(run_id)

    def set_task(self, run_id: str, task: asyncio.Task) -> None:
        run = self._runs.get(run_id)
        if run:
            run.task = task

    def request_stop(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run and run.status == "running":
            run.stop_event.set()
            return True
        return False

    def is_stop_requested(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        return run.stop_event.is_set() if run else False

    async def publish_progress(self, run_id: str, progress: RunProgress) -> None:
        run = self._runs.get(run_id)
        if run:
            try:
                run.progress_queue.put_nowait(progress)
            except asyncio.QueueFull:
                # Drop oldest if full
                try:
                    run.progress_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                run.progress_queue.put_nowait(progress)

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        baseline_score: float | None = None,
        best_score: float | None = None,
        current_score: float | None = None,
        current_iteration: int | None = None,
        total_api_calls: int | None = None,
        stopped_reason: str | None = None,
        progress_message: str | None = None,
    ) -> None:
        run = self._runs.get(run_id)
        if not run:
            return
        if status is not None:
            run.status = status
            if status in ("completed", "stopped", "failed"):
                run.completed_at = datetime.now(timezone.utc)
        if baseline_score is not None:
            run.baseline_score = baseline_score
        if best_score is not None:
            run.best_score = best_score
        if current_score is not None:
            run.current_score = current_score
        if current_iteration is not None:
            run.current_iteration = current_iteration
        if total_api_calls is not None:
            run.total_api_calls = total_api_calls
        if stopped_reason is not None:
            run.stopped_reason = stopped_reason
        if progress_message is not None:
            run.progress_message = progress_message

    def list_runs(self, tenant_id: str | None = None) -> list[ActiveRun]:
        runs = list(self._runs.values())
        if tenant_id:
            runs = [r for r in runs if r.tenant_id == tenant_id]
        return sorted(runs, key=lambda r: r.started_at, reverse=True)

    async def subscribe_progress(
        self, run_id: str
    ) -> AsyncGenerator[str, None]:
        """SSE generator for a run's progress."""
        run = self._runs.get(run_id)
        if not run:
            yield RunProgress(
                run_id=run_id,
                event="error",
                message="Run not found",
            ).to_sse()
            return

        while True:
            try:
                progress = await asyncio.wait_for(
                    run.progress_queue.get(), timeout=30.0
                )
                yield progress.to_sse()
                if progress.event in ("completed", "stopped", "error"):
                    return
            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"
            except asyncio.CancelledError:
                return
