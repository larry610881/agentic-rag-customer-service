"""Wiki BC domain services (Ports).

WikiCompilerService 是 Port — 抽象介面，Infrastructure 實作具體的 LLM 呼叫邏輯。
ExtractedGraph 是編譯過程的中間結果（單一文件產出），
之後由 graph_builder 合併成 WikiGraph。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.domain.rag.value_objects import TokenUsage


@dataclass(frozen=True)
class ExtractedNode:
    """單一文件擷取出的概念節點（中間結果）。"""

    id: str
    label: str
    type: str = "concept"  # concept | entity | process | policy
    summary: str = ""
    source_doc_id: str = ""


@dataclass(frozen=True)
class ExtractedEdge:
    """單一文件擷取出的關係邊（中間結果）。"""

    source: str
    target: str
    relation: str
    confidence: str = "EXTRACTED"  # EXTRACTED | INFERRED | AMBIGUOUS
    confidence_score: float = 1.0


@dataclass(frozen=True)
class ExtractedGraph:
    """從單一文件擷取出的 graph fragment。"""

    nodes: tuple[ExtractedNode, ...] = ()
    edges: tuple[ExtractedEdge, ...] = ()
    usage: TokenUsage | None = None


class WikiCompilerService(ABC):
    """Wiki 編譯 Port — 從文件內容擷取概念 + 關係。

    Infrastructure 實作會呼叫 LLM，但 Domain 層只知道抽象介面。
    """

    @abstractmethod
    async def extract(
        self,
        *,
        document_id: str,
        content: str,
        language: str = "zh-TW",
    ) -> ExtractedGraph:
        """從單一文件內容擷取 graph fragment。

        Args:
            document_id: 文件 ID（會放進節點 source_doc_id）
            content: 文件純文字內容
            language: 語言代碼（影響 LLM prompt 中的 "用繁中回答" 指令）

        Returns:
            ExtractedGraph — 含 nodes/edges/usage，失敗時回傳空 ExtractedGraph。
        """
        ...


@dataclass
class CompileResult:
    """Wiki 編譯完整結果 — Use Case 層使用。"""

    node_count: int = 0
    edge_count: int = 0
    cluster_count: int = 0
    document_count: int = 0
    total_usage: TokenUsage | None = None
    errors: list[str] = field(default_factory=list)
