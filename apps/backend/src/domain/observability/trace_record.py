"""RAG Trace Record — 記錄每次 RAG 查詢的完整鏈路"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class RAGTraceStep:
    """單一步驟的追蹤記錄"""
    name: str  # "embed" | "retrieve" | "score_filter"
    elapsed_ms: float
    metadata: dict | None = None  # chunk_count, scores, etc.


@dataclass
class RAGTraceRecord:
    """完整 RAG 查詢追蹤記錄"""
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    query: str = ""
    tenant_id: str = ""
    message_id: str | None = None
    steps: list[RAGTraceStep] = field(default_factory=list)
    total_ms: float = 0.0
    chunk_count: int = 0
    prompt_snapshot: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_step(self, name: str, elapsed_ms: float, **metadata) -> None:
        """新增一個步驟記錄"""
        step = RAGTraceStep(
            name=name,
            elapsed_ms=round(elapsed_ms, 1),
            metadata=metadata if metadata else None,
        )
        self.steps.append(step)

    def finish(self, total_ms: float) -> None:
        """完成追蹤，記錄總耗時"""
        self.total_ms = round(total_ms, 1)

    def to_dict(self) -> dict:
        """轉為字典格式（供 API/日誌使用）"""
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "tenant_id": self.tenant_id,
            "message_id": self.message_id,
            "steps": [
                {
                    "name": s.name,
                    "elapsed_ms": s.elapsed_ms,
                    **(s.metadata or {}),
                }
                for s in self.steps
            ],
            "total_ms": self.total_ms,
            "chunk_count": self.chunk_count,
            "prompt_snapshot": self.prompt_snapshot,
            "created_at": self.created_at.isoformat(),
        }
