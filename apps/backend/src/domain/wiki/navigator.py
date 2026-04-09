"""Wiki graph navigator — Strategy Pattern Port.

GraphNavigator 是一個抽象介面，定義「從 query 字串 + WikiGraph 找到相關節點」
的能力。具體實作可以有多種策略：

- `KeywordBFSNavigator` (MVP) — LLM 抽關鍵字 + BFS 遍歷
- `SubstringBFSNavigator` (Post-MVP, speculative) — 純字串匹配，適合英文 FAQ
- `ClusterPickerNavigator` (Post-MVP) — Graphify 風格，適合 legacy 文件導入
- `HybridNavigator` (Post-MVP) — keyword + cluster picker fallback
- `EmbeddingNavigator` (Post-MVP) — 向量檢索，需要 pgvector

設計原則：
- Navigator 不依賴任何 infrastructure 細節（純 Domain Port）
- 所有查詢都是 pure function 的概念（無副作用、可重跑）
- 回傳 NavigationResult 列表，供 use case 組成 RAG-compatible sources schema
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.domain.wiki.entity import WikiGraph

# MVP 只支援一個策略；Post-MVP 加入其他
VALID_NAVIGATION_STRATEGIES = ("keyword_bfs",)


@dataclass(frozen=True)
class NavigationResult:
    """單一導航結果 — 一個與 query 相關的節點及其上下文。

    score: 綜合排序分數，越大越相關（navigator 內部演算法決定）
    source_doc_id: 此節點來源的第一個文件 id（多文件貢獻時取第一個）
    path_context: BFS 路徑說明（可選，用於 debug，例如 "seed" 或 "seed→neighbor"）
    """

    node_id: str
    label: str
    summary: str = ""
    score: float = 0.0
    source_doc_id: str = ""
    path_context: str = ""
    related_edges: tuple[str, ...] = field(default_factory=tuple)


class GraphNavigator(ABC):
    """Wiki 查詢的 Strategy Port。

    每個具體 navigator 封裝一種「從 query → nodes」的演算法。
    實作放在 infrastructure/wiki/ 下。
    """

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """回傳 strategy 識別字串，對應 VALID_NAVIGATION_STRATEGIES 的一員。"""
        ...

    @abstractmethod
    async def navigate(
        self,
        *,
        query: str,
        wiki_graph: WikiGraph,
        top_n: int = 8,
    ) -> list[NavigationResult]:
        """從 query 和 WikiGraph 找出最相關的 top_n 個節點。

        Args:
            query: 使用者的原始問題字串
            wiki_graph: 目標 wiki graph 聚合根
            top_n: 最多回傳幾個節點（預設 8）

        Returns:
            list[NavigationResult]，按 score 降序排列。空 list 表示找不到相關節點
            （不要 throw exception，讓 use case 可以回可讀錯誤訊息）。
        """
        ...
