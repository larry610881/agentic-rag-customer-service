"""版本服役成效（spec §13.6 / §14 層次 1）

以 `token_usage_records.config_version_id` 為錨，join 出該版本服役期間的
線上品質訊號。前後對照含時間混淆因子（流量組成變化），UI 需標注
「方向性參考，非嚴格因果」。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VersionMetrics:
    version_id: str
    message_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float | None = None
    # {"L1": 0.82, "L2": 0.91, ...}（線上 eval 平均分，無資料 = 缺 key）
    eval_avg_by_layer: dict[str, float] = field(default_factory=dict)
    feedback_up: int = 0
    feedback_down: int = 0

    @property
    def feedback_positive_rate(self) -> float | None:
        total = self.feedback_up + self.feedback_down
        return self.feedback_up / total if total else None


class VersionMetricsRepository(ABC):
    @abstractmethod
    async def get_metrics(
        self, tenant_id: str, version_id: str
    ) -> VersionMetrics: ...
