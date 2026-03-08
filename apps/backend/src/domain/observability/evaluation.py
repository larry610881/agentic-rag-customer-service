"""RAG Evaluation — 評估結果 Entity

三層評估架構：
- L1: 單次 Tool — Context Precision/Recall per RAG call
- L2: 端到端 — Faithfulness/Relevancy of final answer
- L3: Agent 決策 — ReAct loop efficiency (only for ReAct mode)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class EvalDimension:
    """單一評估維度的結果"""
    name: str  # e.g., "context_precision", "faithfulness", "agent_efficiency"
    score: float  # 0.0 - 1.0
    explanation: str = ""


@dataclass
class EvalResult:
    """完整評估結果"""
    eval_id: str = field(default_factory=lambda: str(uuid4()))
    message_id: str | None = None
    trace_id: str | None = None
    tenant_id: str = ""
    layer: str = "L1"  # "L1" | "L2" | "L3"
    dimensions: list[EvalDimension] = field(default_factory=list)
    model_used: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def avg_score(self) -> float:
        """所有維度的平均分數"""
        if not self.dimensions:
            return 0.0
        return sum(d.score for d in self.dimensions) / len(self.dimensions)

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "message_id": self.message_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "layer": self.layer,
            "dimensions": [
                {"name": d.name, "score": d.score, "explanation": d.explanation}
                for d in self.dimensions
            ],
            "avg_score": round(self.avg_score, 3),
            "model_used": self.model_used,
            "created_at": self.created_at.isoformat(),
        }
