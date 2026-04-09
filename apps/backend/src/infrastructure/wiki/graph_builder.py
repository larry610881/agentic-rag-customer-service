"""Wiki graph builder — 純函式，無 I/O、無 LLM 呼叫。

負責將多個 ExtractedGraph（單一文件結果）合併為單一 WikiGraph：
1. 去重節點（by node id）
2. 累積 edges，以 (source, target, relation) 為 key 去重，confidence 最高者勝出
3. 從 edges 反推 backlinks（target → sources）
4. Louvain community detection 做 clustering（networkx 內建，詳見 CLUSTERING NOTES）

===================
CLUSTERING NOTES — 未來調整方向
===================
目前使用 networkx 3.6+ 內建的 `community.louvain_communities`：
- 品質：約為 Leiden 的 95%，對客服 KB 規模（百～千節點）完全夠用
- 效能：$O(n \\log n)$，對 10k 節點也能在秒級完成
- 可重現：固定 seed=42 → 相同輸入產生相同 cluster

**什麼時候升級到 Leiden？（graspologic）**
觸發條件：
  (1) 單一租戶 node 數超過 10000
  (2) 或 Louvain 產出的 modularity < 0.3（cluster 品質差）
  (3) 或用戶抱怨「語意相近的概念沒被分在同一 cluster」
升級成本：~50MB 額外依賴 + C 編譯，graspologic import 時有時會出 ANSI escape warning

**什麼時候考慮改用 LLM-based clustering？**
觸發條件：
  (1) 需要為每個 cluster 自動產生「可讀的繁中摘要標籤」（目前用 heuristic：最長 label）
  (2) 或需要 semantic clustering（語意相似但圖結構不相連的節點分在一起）
升級成本：每次 compile 多 1-2 次 LLM call；但只需針對 cluster 摘要，token 花費可控

**Resolution 調整**
Louvain 的 `resolution` 參數（預設 1.0）控制 cluster 粒度：
  - resolution > 1.0 → 更細碎的 cluster（更多小群）
  - resolution < 1.0 → 更粗的 cluster（更少大群）
客服 KB 目前用預設值；若發現 cluster 太碎或太粗，調這個就好。

**備份方案：BFS 連通分量（已廢棄）**
早期 MVP 想過用 BFS 找連通分量當 cluster，避免新依賴。但實測發現對
真實 KB（10+ 文件，概念彼此交錯）會產出「全圖唯一一個 cluster」，
等同 clustering 失效。最終決定 networkx 值得加。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict

import networkx as nx

from src.domain.wiki.services import ExtractedEdge, ExtractedGraph

# 邊信心度排序：EXTRACTED > INFERRED > AMBIGUOUS
_CONFIDENCE_RANK = {
    "EXTRACTED": 3,
    "INFERRED": 2,
    "AMBIGUOUS": 1,
}

# Louvain 參數（固定 seed 以保證可重現）
_LOUVAIN_SEED = 42
_LOUVAIN_MAX_LEVEL = 10  # prevent hangs on large sparse graphs


def merge_extracted_graphs(
    graphs: Iterable[ExtractedGraph],
) -> tuple[dict[str, dict], dict[str, dict]]:
    """合併多個 ExtractedGraph 為 (nodes_dict, edges_dict)。

    節點去重規則：
        - 相同 id 只保留第一次出現的 label + type + summary
        - source_doc_ids 累積為 list（多文件提到同一節點）

    邊合併規則：
        - 以 (source, target, relation) 為 key 去重
        - 衝突時保留 confidence 最高者；同等 confidence 取 score 最大者
    """
    nodes: dict[str, dict] = {}
    source_doc_sets: dict[str, set[str]] = defaultdict(set)
    edges_by_key: dict[tuple[str, str, str], ExtractedEdge] = {}

    for g in graphs:
        for n in g.nodes:
            if n.id not in nodes:
                nodes[n.id] = {
                    "label": n.label,
                    "type": n.type or "concept",
                    "summary": n.summary,
                    "source_doc_ids": [],
                }
            if n.source_doc_id:
                source_doc_sets[n.id].add(n.source_doc_id)

        for e in g.edges:
            key = (e.source, e.target, e.relation)
            existing = edges_by_key.get(key)
            if existing is None or _edge_beats(e, existing):
                edges_by_key[key] = e

    for node_id, doc_set in source_doc_sets.items():
        nodes[node_id]["source_doc_ids"] = sorted(doc_set)

    edges: dict[str, dict] = {}
    for (src, tgt, rel), edge in edges_by_key.items():
        edge_id = f"{src}--{rel}--{tgt}"
        edges[edge_id] = {
            "source": src,
            "target": tgt,
            "relation": rel,
            "confidence": edge.confidence,
            "score": edge.confidence_score,
        }

    return nodes, edges


def _edge_beats(new: ExtractedEdge, existing: ExtractedEdge) -> bool:
    new_rank = _CONFIDENCE_RANK.get(new.confidence, 0)
    existing_rank = _CONFIDENCE_RANK.get(existing.confidence, 0)
    if new_rank != existing_rank:
        return new_rank > existing_rank
    return new.confidence_score > existing.confidence_score


def build_backlinks(edges: dict[str, dict]) -> dict[str, list[str]]:
    """From edges dict, compute backlinks: target_node → [source_nodes]."""
    backlinks: dict[str, set[str]] = defaultdict(set)
    for edge in edges.values():
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if src and tgt:
            backlinks[tgt].add(src)
    return {k: sorted(v) for k, v in backlinks.items()}


def detect_clusters_louvain(
    nodes: dict[str, dict],
    edges: dict[str, dict],
    *,
    resolution: float = 1.0,
) -> list[dict]:
    """Louvain community detection via networkx.

    Args:
        nodes: merged nodes dict (from merge_extracted_graphs)
        edges: merged edges dict (from merge_extracted_graphs)
        resolution: >1.0 → finer clusters; <1.0 → coarser clusters (default 1.0)

    Returns:
        list of cluster dicts sorted by size desc, each with:
          {id, label, node_ids, summary}

    Notes:
        - Isolate nodes (no edges) each become their own single-node cluster
        - Cluster label is heuristically chosen as the longest node label in it
        - seed is fixed for determinism (same input → same cluster)
    """
    if not nodes:
        return []

    # Build an undirected graph (Louvain ignores direction)
    G: nx.Graph = nx.Graph()
    for node_id in nodes.keys():
        G.add_node(node_id)
    for edge in edges.values():
        src, tgt = edge.get("source"), edge.get("target")
        if src in nodes and tgt in nodes and src != tgt:
            # Use confidence score as edge weight for weighted Louvain
            weight = float(edge.get("score") or 1.0)
            if G.has_edge(src, tgt):
                # Aggregate duplicate edges (different relations between same
                # two nodes) — take max weight
                G[src][tgt]["weight"] = max(
                    G[src][tgt]["weight"], weight
                )
            else:
                G.add_edge(src, tgt, weight=weight)

    # Edge-less graph: every node its own cluster
    if G.number_of_edges() == 0:
        return _build_clusters(
            [[n] for n in sorted(G.nodes())], nodes
        )

    # Separate isolates (Louvain silently drops them)
    isolates = [n for n in G.nodes() if G.degree(n) == 0]
    connected = G.subgraph([n for n in G.nodes() if G.degree(n) > 0])

    communities_list: list[list[str]] = []
    if connected.number_of_nodes() > 0:
        raw_communities = nx.community.louvain_communities(
            connected,
            weight="weight",
            resolution=resolution,
            seed=_LOUVAIN_SEED,
            max_level=_LOUVAIN_MAX_LEVEL,
        )
        communities_list.extend(sorted(c) for c in raw_communities)

    # Each isolate becomes its own cluster
    for n in sorted(isolates):
        communities_list.append([n])

    return _build_clusters(communities_list, nodes)


def _build_clusters(
    communities: list[list[str]],
    nodes: dict[str, dict],
) -> list[dict]:
    """Convert raw community node lists into cluster dicts sorted by size."""
    result: list[dict] = []
    # Sort by size desc for deterministic ordering
    communities_sorted = sorted(
        communities, key=lambda c: (-len(c), c[0] if c else "")
    )
    for i, component in enumerate(communities_sorted):
        if not component:
            continue
        # Pick representative label = longest node label in the component
        rep_label = max(
            (nodes[nid]["label"] for nid in component if nid in nodes),
            key=lambda s: len(s or ""),
            default="",
        )
        result.append(
            {
                "id": f"cluster-{i:04d}",
                "label": rep_label or f"群組 {i + 1}",
                "node_ids": sorted(component),
                "summary": "",
            }
        )
    return result


def dump_extracted_graph(graph: ExtractedGraph) -> dict:
    """Debug helper — convert ExtractedGraph to plain dict for logging."""
    return {
        "nodes": [asdict(n) for n in graph.nodes],
        "edges": [asdict(e) for e in graph.edges],
    }
