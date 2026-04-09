"""Wiki graph_builder pure-function unit tests.

驗證合併、backlinks、Louvain clustering 的邏輯。
"""

from src.domain.wiki.services import (
    ExtractedEdge,
    ExtractedGraph,
    ExtractedNode,
)
from src.infrastructure.wiki.graph_builder import (
    build_backlinks,
    detect_clusters_louvain,
    merge_extracted_graphs,
)


def _make_graph(
    doc_id: str,
    nodes: list[tuple[str, str]],
    edges: list[tuple[str, str, str, str, float]],
) -> ExtractedGraph:
    return ExtractedGraph(
        nodes=tuple(
            ExtractedNode(id=nid, label=lbl, source_doc_id=doc_id)
            for nid, lbl in nodes
        ),
        edges=tuple(
            ExtractedEdge(
                source=s, target=t, relation=r, confidence=c, confidence_score=sc
            )
            for s, t, r, c, sc in edges
        ),
    )


class TestMergeExtractedGraphs:
    def test_empty_list(self):
        nodes, edges = merge_extracted_graphs([])
        assert nodes == {}
        assert edges == {}

    def test_single_graph(self):
        g = _make_graph(
            "doc-1",
            [("n1", "退貨"), ("n2", "退款")],
            [("n1", "n2", "triggers", "EXTRACTED", 1.0)],
        )
        nodes, edges = merge_extracted_graphs([g])
        assert set(nodes.keys()) == {"n1", "n2"}
        assert nodes["n1"]["label"] == "退貨"
        assert nodes["n1"]["source_doc_ids"] == ["doc-1"]
        assert len(edges) == 1
        edge_id = "n1--triggers--n2"
        assert edges[edge_id]["confidence"] == "EXTRACTED"

    def test_dedup_nodes_across_docs(self):
        g1 = _make_graph("doc-1", [("退貨", "退貨")], [])
        g2 = _make_graph("doc-2", [("退貨", "退貨政策")], [])
        nodes, _ = merge_extracted_graphs([g1, g2])
        # Label from first graph wins (deterministic)
        assert nodes["退貨"]["label"] == "退貨"
        # Both docs contributed
        assert nodes["退貨"]["source_doc_ids"] == ["doc-1", "doc-2"]

    def test_edge_confidence_priority(self):
        """EXTRACTED edge should override INFERRED."""
        g1 = _make_graph(
            "doc-1",
            [("a", "A"), ("b", "B")],
            [("a", "b", "related", "INFERRED", 0.8)],
        )
        g2 = _make_graph(
            "doc-2",
            [("a", "A"), ("b", "B")],
            [("a", "b", "related", "EXTRACTED", 1.0)],
        )
        _, edges = merge_extracted_graphs([g1, g2])
        edge_id = "a--related--b"
        assert edges[edge_id]["confidence"] == "EXTRACTED"
        assert edges[edge_id]["score"] == 1.0

    def test_edge_score_tiebreak(self):
        """Same confidence → higher score wins."""
        g1 = _make_graph(
            "doc-1",
            [("a", "A"), ("b", "B")],
            [("a", "b", "related", "INFERRED", 0.6)],
        )
        g2 = _make_graph(
            "doc-2",
            [("a", "A"), ("b", "B")],
            [("a", "b", "related", "INFERRED", 0.9)],
        )
        _, edges = merge_extracted_graphs([g1, g2])
        assert edges["a--related--b"]["score"] == 0.9

    def test_different_relations_are_separate_edges(self):
        g = _make_graph(
            "doc-1",
            [("a", "A"), ("b", "B")],
            [
                ("a", "b", "requires", "EXTRACTED", 1.0),
                ("a", "b", "references", "EXTRACTED", 1.0),
            ],
        )
        _, edges = merge_extracted_graphs([g])
        assert len(edges) == 2


class TestBuildBacklinks:
    def test_empty(self):
        assert build_backlinks({}) == {}

    def test_single_edge(self):
        edges = {"e1": {"source": "a", "target": "b", "relation": "r"}}
        assert build_backlinks(edges) == {"b": ["a"]}

    def test_fan_in(self):
        """多個 source 指向同一 target."""
        edges = {
            "e1": {"source": "a", "target": "z"},
            "e2": {"source": "b", "target": "z"},
            "e3": {"source": "c", "target": "z"},
        }
        bl = build_backlinks(edges)
        assert bl == {"z": ["a", "b", "c"]}

    def test_ignores_self_references(self):
        edges = {"e1": {"source": "a", "target": "a"}}
        bl = build_backlinks(edges)
        assert bl == {"a": ["a"]}


class TestDetectClustersLouvain:
    def test_empty(self):
        assert detect_clusters_louvain({}, {}) == []

    def test_isolates_each_own_cluster(self):
        """No edges → every node is its own cluster."""
        concept = {"source_doc_ids": [], "type": "concept", "summary": ""}
        nodes = {
            "n1": {"label": "A", **concept},
            "n2": {"label": "B", **concept},
            "n3": {"label": "C", **concept},
        }
        clusters = detect_clusters_louvain(nodes, {})
        assert len(clusters) == 3
        cluster_node_sets = {tuple(c["node_ids"]) for c in clusters}
        assert cluster_node_sets == {("n1",), ("n2",), ("n3",)}

    def test_connected_subgraphs_grouped(self):
        """Connected components should be in the same cluster."""
        common = {"source_doc_ids": [], "summary": ""}
        nodes = {
            "a": {"label": "退貨政策", "type": "policy", **common},
            "b": {"label": "退款", "type": "concept", **common},
            "c": {"label": "配送", "type": "concept", **common},
        }
        edges = {
            "e1": {
                "source": "a",
                "target": "b",
                "relation": "triggers",
                "confidence": "EXTRACTED",
                "score": 1.0,
            },
        }
        clusters = detect_clusters_louvain(nodes, edges)
        # a,b are connected, c is isolate
        assert len(clusters) == 2
        # Largest cluster first
        assert sorted(clusters[0]["node_ids"]) == ["a", "b"]
        # Rep label = longest, "退貨政策" (4 chars) > "退款" (2 chars)
        assert clusters[0]["label"] == "退貨政策"
        assert clusters[1]["node_ids"] == ["c"]

    def test_louvain_splits_dense_graph_into_communities(self):
        """Two dense communities loosely connected should be split."""
        # Community 1: a,b,c all connected
        # Community 2: x,y,z all connected
        # Single bridge b-x
        nodes = {
            nid: {
                "label": nid.upper(),
                "source_doc_ids": [],
                "type": "concept",
                "summary": "",
            }
            for nid in ["a", "b", "c", "x", "y", "z"]
        }
        edges = {}

        def add_edge(eid, s, t):
            edges[eid] = {
                "source": s,
                "target": t,
                "relation": "r",
                "confidence": "EXTRACTED",
                "score": 1.0,
            }

        add_edge("e1", "a", "b")
        add_edge("e2", "b", "c")
        add_edge("e3", "a", "c")
        add_edge("e4", "x", "y")
        add_edge("e5", "y", "z")
        add_edge("e6", "x", "z")
        add_edge("e7", "b", "x")  # Bridge

        clusters = detect_clusters_louvain(nodes, edges)
        # Louvain should split into 2 communities (not 1 giant)
        assert len(clusters) == 2
        sizes = sorted(len(c["node_ids"]) for c in clusters)
        assert sizes == [3, 3]

    def test_deterministic_across_runs(self):
        """Same input → same cluster output (seed is fixed)."""
        nodes = {
            nid: {
                "label": nid,
                "source_doc_ids": [],
                "type": "concept",
                "summary": "",
            }
            for nid in ["a", "b", "c", "d", "e"]
        }
        edges = {
            "e1": {
                "source": "a",
                "target": "b",
                "relation": "r",
                "confidence": "EXTRACTED",
                "score": 1.0,
            },
            "e2": {
                "source": "b",
                "target": "c",
                "relation": "r",
                "confidence": "EXTRACTED",
                "score": 1.0,
            },
            "e3": {
                "source": "d",
                "target": "e",
                "relation": "r",
                "confidence": "EXTRACTED",
                "score": 1.0,
            },
        }
        c1 = detect_clusters_louvain(nodes, edges)
        c2 = detect_clusters_louvain(nodes, edges)
        # Same ids + same order
        assert [c["node_ids"] for c in c1] == [c["node_ids"] for c in c2]

    def test_cluster_label_picks_longest(self):
        nodes = {
            "n1": {
                "label": "短",
                "source_doc_ids": [],
                "type": "concept",
                "summary": "",
            },
            "n2": {
                "label": "比較長的標籤",
                "source_doc_ids": [],
                "type": "concept",
                "summary": "",
            },
        }
        edges = {
            "e1": {
                "source": "n1",
                "target": "n2",
                "relation": "r",
                "confidence": "EXTRACTED",
                "score": 1.0,
            },
        }
        clusters = detect_clusters_louvain(nodes, edges)
        assert clusters[0]["label"] == "比較長的標籤"

    def test_cluster_ids_have_deterministic_ordering(self):
        """Largest cluster → cluster-0000, next → 0001 etc."""
        nodes = {}
        edges = {}
        # Big cluster: a,b,c,d
        for nid in ["a", "b", "c", "d"]:
            nodes[nid] = {
                "label": nid,
                "source_doc_ids": [],
                "type": "concept",
                "summary": "",
            }
        # Small cluster: x,y
        for nid in ["x", "y"]:
            nodes[nid] = {
                "label": nid,
                "source_doc_ids": [],
                "type": "concept",
                "summary": "",
            }
        i = 0
        for s, t in [("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")]:
            edges[f"e{i}"] = {
                "source": s,
                "target": t,
                "relation": "r",
                "confidence": "EXTRACTED",
                "score": 1.0,
            }
            i += 1
        edges[f"e{i}"] = {
            "source": "x",
            "target": "y",
            "relation": "r",
            "confidence": "EXTRACTED",
            "score": 1.0,
        }
        clusters = detect_clusters_louvain(nodes, edges)
        assert clusters[0]["id"] == "cluster-0000"
        assert len(clusters[0]["node_ids"]) >= len(clusters[-1]["node_ids"])
