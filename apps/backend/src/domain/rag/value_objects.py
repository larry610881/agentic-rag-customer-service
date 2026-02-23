"""RAG 領域值物件"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    """向量搜尋結果"""

    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    """RAG 回答來源引用"""

    document_name: str
    content_snippet: str
    score: float
    chunk_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "content_snippet": self.content_snippet,
            "score": self.score,
            "chunk_id": self.chunk_id,
        }


@dataclass(frozen=True)
class TokenUsage:
    """LLM Token 使用量"""

    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float = 0.0

    @staticmethod
    def zero(model: str = "unknown") -> TokenUsage:
        return TokenUsage(
            model=model,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=0.0,
        )

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            model=self.model,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            estimated_cost=self.estimated_cost + other.estimated_cost,
        )


@dataclass(frozen=True)
class LLMResult:
    """LLM 生成結果（含 token 使用量）"""

    text: str
    usage: TokenUsage


@dataclass(frozen=True)
class RAGResponse:
    """RAG 查詢回應"""

    answer: str
    sources: list[Source]
    query: str
    tenant_id: str
    knowledge_base_id: str
    usage: TokenUsage | None = None
