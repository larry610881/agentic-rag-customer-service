from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.eval_dataset.value_objects import EvalDatasetId, EvalTestCaseId


@dataclass
class EvalTestCase:
    id: EvalTestCaseId = field(default_factory=EvalTestCaseId)
    dataset_id: str = ""
    case_id: str = ""
    question: str = ""
    priority: str = "P1"
    category: str = ""
    conversation_history: list[dict] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EvalDataset:
    id: EvalDatasetId = field(default_factory=EvalDatasetId)
    tenant_id: str = ""
    bot_id: str | None = None
    name: str = ""
    description: str = ""
    target_prompt: str = "base_prompt"
    agent_mode: str = "router"
    default_assertions: list[dict[str, Any]] = field(default_factory=list)
    cost_config: dict[str, Any] = field(default_factory=dict)
    include_security: bool = True
    test_cases: list[EvalTestCase] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
