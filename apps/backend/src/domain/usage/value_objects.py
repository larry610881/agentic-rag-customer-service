"""Usage 領域值物件"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UsageSummary:
    """租戶 Token 使用摘要"""

    tenant_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    by_model: dict[str, int] = field(default_factory=dict)
    by_request_type: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelCostStat:
    """每模型 Token 成本統計"""

    model: str
    message_count: int
    input_tokens: int
    output_tokens: int
    avg_latency_ms: float
    estimated_cost: float
