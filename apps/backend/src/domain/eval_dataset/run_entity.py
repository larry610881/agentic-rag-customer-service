"""Optimization run domain entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class OptimizationIteration:
    id: str = ""
    run_id: str = ""
    iteration: int = 0
    tenant_id: str = ""
    target_field: str = ""
    bot_id: str | None = None
    prompt_snapshot: str = ""
    score: float = 0.0
    passed_count: int = 0
    total_count: int = 0
    is_best: bool = False
    details: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OptimizationRunSummary:
    """Summary of a run (for list view)."""

    run_id: str = ""
    tenant_id: str = ""
    dataset_id: str = ""
    dataset_name: str = ""
    target_field: str = ""
    bot_id: str | None = None
    status: str = "running"  # running | completed | stopped | failed
    baseline_score: float = 0.0
    best_score: float = 0.0
    current_iteration: int = 0
    max_iterations: int = 0
    total_api_calls: int = 0
    stopped_reason: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
