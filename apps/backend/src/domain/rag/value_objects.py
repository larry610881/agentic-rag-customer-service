"""RAG 領域值物件"""

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
class RAGResponse:
    """RAG 查詢回應"""

    answer: str
    sources: list[Source]
    query: str
    tenant_id: str
    knowledge_base_id: str
