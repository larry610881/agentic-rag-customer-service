"""PromptGateRun — 閘門驗證 run（spec §3.4）

生命週期：queued → running → completed | error。
與版本狀態機的接線：run 啟動時 version.mark_validating(run_id)，
run 完成時 version.mark_validation_result(passed)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.prompt_gate.entity import InvalidVersionTransitionError

RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_ERROR = "error"

RUN_VERDICT_PASS = "pass"
RUN_VERDICT_FAIL = "fail"


@dataclass
class PromptGateRun:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    bot_id: str = ""
    version_id: str = ""
    status: str = RUN_QUEUED
    verdict: str | None = None
    fail_reasons: list[str] = field(default_factory=list)
    dataset_ids: list[str] = field(default_factory=list)
    repeats: int = 3
    soft_threshold: float = 0.8
    total_cases: int | None = None
    hard_failed_cases: int | None = None
    soft_pass_rate: float | None = None
    unstable_cases: int | None = None
    est_cost: float | None = None
    actual_cost: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    details: dict | None = None
    error_message: str | None = None
    triggered_by: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def mark_running(self) -> None:
        if self.status != RUN_QUEUED:
            raise InvalidVersionTransitionError(self.status, "start-run")
        self.status = RUN_RUNNING
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self, *, passed: bool) -> None:
        if self.status != RUN_RUNNING:
            raise InvalidVersionTransitionError(self.status, "complete-run")
        self.status = RUN_COMPLETED
        self.verdict = RUN_VERDICT_PASS if passed else RUN_VERDICT_FAIL
        self.completed_at = datetime.now(timezone.utc)

    def mark_error(self, message: str) -> None:
        self.status = RUN_ERROR
        self.error_message = message[:2000]
        self.completed_at = datetime.now(timezone.utc)
