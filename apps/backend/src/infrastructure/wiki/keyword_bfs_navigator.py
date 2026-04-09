"""KeywordBFSNavigator — Wiki 查詢的 MVP 實作（方案 #1）。

演算法流程：
1. 用 LLM 從 query 抽出 3-5 個繁中關鍵字（max_tokens=100, temperature=0）
2. 對 wiki_graph.nodes 的 label + summary 做 partial string match 找 seed 節點
   - 每個關鍵字命中累加分數
3. BFS 從 seeds 沿 edges 走 max_depth=2，依 edge confidence 加權
4. 綜合排序: (seed_score + BFS_distance_inverse + edge_confidence)
5. Fallback：若 BFS 結果 < 2 個節點，補上 seed 所在 cluster 的全部節點
6. 容錯：LLM 失敗 → 降級到字串 unigram 匹配（取 query 中 1-2 字詞）

設計原則：
- 純函式為主，I/O 只在 LLM 抽關鍵字那一步
- 後段全部 deterministic，可寫單元測試
- 不引入新依賴（用內建字串操作 + 已裝的 networkx 也不需要，自己 BFS）
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass

from src.domain.rag.services import LLMService
from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.navigator import GraphNavigator, NavigationResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


_KEYWORD_EXTRACTION_PROMPT = """你是繁體中文客服查詢分析器。\
從使用者問題中抽取 3-5 個關鍵字，幫助 Wiki 知識庫查詢系統定位相關節點。

規則：
- 只輸出 JSON 陣列，不要任何解釋
- 每個關鍵字 2-6 個繁體中文字
- 優先抽取「業務名詞、動作、政策、流程」相關詞
- 避免無意義的虛詞、語助詞
- 同義詞請給出最常用的版本（例如「歸還」→「退貨」）

範例：
問題: "我買的東西可以寄回去嗎？"
輸出: ["退貨", "退貨流程", "退貨政策"]

問題: "錢什麼時候會還我？"
輸出: ["退款", "退款時間", "到帳"]

直接輸出 JSON 陣列。"""


_USER_PROMPT_TEMPLATE = """使用者問題：{query}

關鍵字 JSON 陣列："""


_JSON_ARRAY_RE = re.compile(r"\[\s*(?:\"[^\"]*\"\s*,?\s*)+\]")


# 中文 stopword（避免 fallback 抓到無意義字）
_STOPWORDS = frozenset(
    [
        "的",
        "了",
        "是",
        "我",
        "你",
        "他",
        "她",
        "在",
        "有",
        "會",
        "嗎",
        "呢",
        "啊",
        "吧",
        "什麼",
        "怎麼",
        "為什",
        "如何",
        "可以",
        "可不可以",
        "要",
        "想",
        "請問",
        "一下",
        "這個",
        "那個",
        "東西",
    ]
)


@dataclass
class _SeedHit:
    """中間結果：seed node 命中資訊。"""

    node_id: str
    score: float
    matched_keywords: list[str]


class KeywordBFSNavigator(GraphNavigator):
    """方案 #1：LLM 抽關鍵字 + BFS 遍歷 — Wiki 查詢的 MVP 預設策略。"""

    def __init__(
        self,
        llm_service: LLMService,
        *,
        max_keywords: int = 5,
        max_depth: int = 2,
        seed_score_weight: float = 1.0,
        bfs_decay: float = 0.5,
        edge_confidence_bonus: float = 0.3,
    ) -> None:
        self._llm = llm_service
        self._max_keywords = max_keywords
        self._max_depth = max_depth
        self._seed_score_weight = seed_score_weight
        self._bfs_decay = bfs_decay
        self._edge_confidence_bonus = edge_confidence_bonus

    @property
    def strategy_name(self) -> str:
        return "keyword_bfs"

    async def navigate(
        self,
        *,
        query: str,
        wiki_graph: WikiGraph,
        top_n: int = 8,
    ) -> list[NavigationResult]:
        if not query or not query.strip():
            return []
        if not wiki_graph.nodes:
            return []

        # Step 1: extract keywords (LLM with fallback)
        keywords = await self._extract_keywords(query)
        if not keywords:
            keywords = self._fallback_unigram_keywords(query)
        if not keywords:
            logger.info(
                "wiki.navigator.no_keywords",
                query_preview=query[:30],
            )
            return []

        # Step 2: find seed nodes by matching keywords against label+summary
        seeds = self._find_seeds(keywords, wiki_graph)
        if not seeds:
            logger.info(
                "wiki.navigator.no_seeds",
                keywords=keywords,
                node_count=len(wiki_graph.nodes),
            )
            return []

        # Step 3: BFS traversal
        scored_nodes = self._bfs_with_scoring(seeds, wiki_graph)

        # Step 4: fallback — if BFS yielded too few, expand seed cluster
        if len(scored_nodes) < 2:
            scored_nodes = self._expand_via_clusters(
                seeds, wiki_graph, scored_nodes
            )

        # Step 5: rank + take top_n + build NavigationResult
        ranked = sorted(
            scored_nodes.items(), key=lambda kv: (-kv[1], kv[0])
        )[:top_n]
        return [
            self._build_result(node_id, score, wiki_graph, seeds)
            for node_id, score in ranked
        ]

    # ------------------------------------------------------------------
    # Keyword extraction
    # ------------------------------------------------------------------

    async def _extract_keywords(self, query: str) -> list[str]:
        try:
            result = await self._llm.generate(
                system_prompt=_KEYWORD_EXTRACTION_PROMPT,
                user_message=_USER_PROMPT_TEMPLATE.format(query=query),
                context="",
                temperature=0.0,
                max_tokens=100,
            )
        except Exception as exc:
            logger.warning(
                "wiki.navigator.llm_failed",
                error=str(exc),
                query_preview=query[:30],
            )
            return []

        return self._parse_keywords(result.text)

    @staticmethod
    def _parse_keywords(text: str) -> list[str]:
        if not text:
            return []
        stripped = text.strip()
        # Try direct parse first
        try:
            data = json.loads(stripped)
            if isinstance(data, list):
                return [str(k).strip() for k in data if str(k).strip()]
        except (json.JSONDecodeError, ValueError):
            pass
        # Try regex extraction
        m = _JSON_ARRAY_RE.search(stripped)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, list):
                    return [str(k).strip() for k in data if str(k).strip()]
            except (json.JSONDecodeError, ValueError):
                pass
        return []

    @staticmethod
    def _fallback_unigram_keywords(query: str) -> list[str]:
        """LLM 失敗時的降級策略：取 query 中非 stopword 的 2 字以上連續中文片段。

        簡化版：直接切 2-gram，過濾 stopword 命中超過半數的片段。
        """
        # Strip punctuation first
        cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", query)
        tokens = cleaned.split()
        keywords: list[str] = []
        for token in tokens:
            if not token:
                continue
            if len(token) >= 2 and token not in _STOPWORDS:
                keywords.append(token)
            # Also try 2-grams within longer tokens
            if len(token) > 3:
                for i in range(len(token) - 1):
                    bigram = token[i : i + 2]
                    if bigram not in _STOPWORDS and bigram not in keywords:
                        keywords.append(bigram)
        return keywords[:5]

    # ------------------------------------------------------------------
    # Seed matching
    # ------------------------------------------------------------------

    def _find_seeds(
        self, keywords: list[str], wiki_graph: WikiGraph
    ) -> dict[str, _SeedHit]:
        """For each node, count how many keywords match its label or summary.

        Returns dict[node_id, _SeedHit] for nodes with at least one match.
        Score = sum of keyword length × match_location_weight.
        """
        seeds: dict[str, _SeedHit] = {}
        for node_id, node in wiki_graph.nodes.items():
            label = str(node.get("label", "") or "")
            summary = str(node.get("summary", "") or "")
            matched: list[str] = []
            score = 0.0
            for kw in keywords:
                if not kw:
                    continue
                if kw in label:
                    # Label match weighted higher
                    score += len(kw) * 2.0
                    matched.append(kw)
                elif kw in summary:
                    score += len(kw) * 1.0
                    matched.append(kw)
            if matched:
                seeds[node_id] = _SeedHit(
                    node_id=node_id,
                    score=score,
                    matched_keywords=matched,
                )
        return seeds

    # ------------------------------------------------------------------
    # BFS traversal
    # ------------------------------------------------------------------

    def _build_adjacency(
        self, wiki_graph: WikiGraph
    ) -> dict[str, list[tuple[str, float, str]]]:
        """Build undirected adjacency list with edge weights.

        adjacency[node_id] = [(neighbor_id, edge_score, edge_id), ...]
        """
        adj: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        for edge_id, edge in wiki_graph.edges.items():
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if not src or not tgt or src == tgt:
                continue
            score = float(edge.get("score", 1.0) or 1.0)
            confidence = str(edge.get("confidence", "EXTRACTED"))
            # Boost EXTRACTED, dampen AMBIGUOUS
            if confidence == "EXTRACTED":
                score = max(score, 1.0)
            elif confidence == "AMBIGUOUS":
                score = score * 0.4
            adj[src].append((tgt, score, edge_id))
            adj[tgt].append((src, score, edge_id))
        return adj

    def _bfs_with_scoring(
        self,
        seeds: dict[str, _SeedHit],
        wiki_graph: WikiGraph,
    ) -> dict[str, float]:
        """BFS from all seeds, accumulate per-node score by best path."""
        adj = self._build_adjacency(wiki_graph)
        scored: dict[str, float] = {}

        # Initialize seed scores
        for node_id, hit in seeds.items():
            scored[node_id] = hit.score * self._seed_score_weight

        # BFS layer by layer from all seeds simultaneously
        frontier = list(seeds.keys())
        for depth in range(1, self._max_depth + 1):
            decay = self._bfs_decay**depth
            next_frontier: list[str] = []
            for node_id in frontier:
                seed_score = scored.get(node_id, 0)
                for neighbor, edge_score, _ in adj.get(node_id, []):
                    contribution = (
                        seed_score * decay
                        + edge_score * self._edge_confidence_bonus
                    )
                    existing = scored.get(neighbor, 0)
                    if contribution > existing:
                        scored[neighbor] = contribution
                        next_frontier.append(neighbor)
            frontier = next_frontier
            if not frontier:
                break
        return scored

    def _expand_via_clusters(
        self,
        seeds: dict[str, _SeedHit],
        wiki_graph: WikiGraph,
        existing: dict[str, float],
    ) -> dict[str, float]:
        """Fallback: if BFS returned too few nodes, add nodes from seed clusters."""
        # Find clusters containing any seed node
        relevant_cluster_node_ids: set[str] = set()
        seed_node_ids = set(seeds.keys())
        for cluster in wiki_graph.clusters:
            cluster_node_ids = set(cluster.get("node_ids", []))
            if cluster_node_ids & seed_node_ids:
                relevant_cluster_node_ids.update(cluster_node_ids)

        # Add cluster members with low (but non-zero) score
        result = dict(existing)
        for nid in relevant_cluster_node_ids:
            if nid not in result:
                result[nid] = 0.5  # Small fallback score
        return result

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    def _build_result(
        self,
        node_id: str,
        score: float,
        wiki_graph: WikiGraph,
        seeds: dict[str, _SeedHit],
    ) -> NavigationResult:
        node = wiki_graph.nodes.get(node_id, {})
        source_doc_ids = node.get("source_doc_ids") or []
        source_doc_id = source_doc_ids[0] if source_doc_ids else ""

        # Path context: is this a seed or a neighbor?
        if node_id in seeds:
            path_context = (
                f"seed (matched: {','.join(seeds[node_id].matched_keywords)})"
            )
        else:
            path_context = "neighbor"

        # Collect outgoing edges for context
        related_edge_ids: list[str] = []
        for edge_id, edge in wiki_graph.edges.items():
            if edge.get("source") == node_id or edge.get("target") == node_id:
                related_edge_ids.append(edge_id)
                if len(related_edge_ids) >= 5:
                    break

        return NavigationResult(
            node_id=node_id,
            label=str(node.get("label", "") or ""),
            summary=str(node.get("summary", "") or ""),
            score=round(score, 4),
            source_doc_id=source_doc_id,
            path_context=path_context,
            related_edges=tuple(related_edge_ids),
        )
