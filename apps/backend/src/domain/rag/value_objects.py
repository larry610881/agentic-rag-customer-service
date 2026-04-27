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
    document_id: str = ""
    # QualityEdit.1 P0/P1: 支援「從 feedback / L1 低分跳到 KB Studio 修正」需要 kb_id
    kb_id: str = ""
    # query_dm_with_image 工具用：DM 子頁的 PNG signed URL + 頁碼。
    # 一般 rag_query 來源這兩欄會是空字串 / 0；前端 SourceImageGallery
    # 用 image_url 是否為空來判斷要不要渲染圖卡。
    image_url: str = ""
    page_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "content_snippet": self.content_snippet,
            "score": self.score,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "kb_id": self.kb_id,
            "image_url": self.image_url,
            "page_number": self.page_number,
        }


@dataclass(frozen=True)
class TokenUsage:
    """LLM Token 使用量

    total_tokens 為 @property（= input + output + cache_read + cache_creation），
    不再是 field — 避免 caller 手動組 total 時忘記加 cache 的 bug（Carrefour
    5.14M cache tokens 沒扣 quota 事件）。DB 寫入的 total_tokens 欄位一律透過
    此 property 讀，保證 ledger.deduct 與 token_usage_records 對齊。
    """

    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float = 0.0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )

    @staticmethod
    def zero(model: str = "unknown") -> TokenUsage:
        return TokenUsage(
            model=model,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
        )

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            model=self.model,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            estimated_cost=self.estimated_cost + other.estimated_cost,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
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
