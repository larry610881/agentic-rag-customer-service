from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostConfig:
    token_budget: int = 2000
    quality_weight: float = 0.85
    cost_weight: float = 0.15


@dataclass
class PromptTarget:
    level: str  # "system" | "bot"
    field: str  # "base_prompt" | "system_prompt"
    bot_id: str | None = None
    tenant_id: str = ""


@dataclass
class OptimizationConfig:
    api_base_url: str = "http://localhost:8001"
    api_token: str = ""
    db_url: str = ""
    target: PromptTarget = field(
        default_factory=lambda: PromptTarget(level="bot", field="system_prompt")
    )
    max_iterations: int = 20
    patience: int = 5
    budget: int = 200  # max total API calls
    mutator_model: str = "gpt-4o-mini"
    cascade_mode: bool = False
    cost_config: CostConfig = field(default_factory=CostConfig)
    dry_run: bool = False  # eval only, no mutation
