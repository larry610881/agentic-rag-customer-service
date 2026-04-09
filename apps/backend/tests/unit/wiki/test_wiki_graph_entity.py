"""WikiGraph domain entity unit tests."""

from datetime import datetime, timezone

from src.domain.wiki.entity import WikiCluster, WikiEdge, WikiGraph, WikiNode
from src.domain.wiki.value_objects import (
    EdgeConfidence,
    WikiGraphId,
    WikiNodeId,
    WikiStatus,
)


class TestWikiGraphEntity:
    def test_default_values(self):
        g = WikiGraph()
        assert isinstance(g.id, WikiGraphId)
        assert g.tenant_id == ""
        assert g.bot_id == ""
        assert g.kb_id == ""
        assert g.status == WikiStatus.PENDING.value
        assert g.nodes == {}
        assert g.edges == {}
        assert g.backlinks == {}
        assert g.clusters == []
        assert g.metadata == {}
        assert g.compiled_at is None
        assert isinstance(g.created_at, datetime)
        assert isinstance(g.updated_at, datetime)

    def test_node_count_and_edge_count(self):
        g = WikiGraph(
            tenant_id="t-001",
            bot_id="b-001",
            kb_id="kb-001",
            nodes={
                "n1": {"label": "退貨流程"},
                "n2": {"label": "退款政策"},
                "n3": {"label": "物流狀態"},
            },
            edges={
                "e1": {"source": "n1", "target": "n2", "relation": "requires"},
                "e2": {"source": "n2", "target": "n3", "relation": "references"},
            },
        )
        assert g.node_count == 3
        assert g.edge_count == 2

    def test_compiled_at_can_be_set(self):
        now = datetime.now(timezone.utc)
        g = WikiGraph(compiled_at=now)
        assert g.compiled_at == now

    def test_backlinks_structure(self):
        g = WikiGraph(
            backlinks={"n2": ["n1", "n3"], "n3": ["n2"]},
        )
        assert g.backlinks["n2"] == ["n1", "n3"]
        assert g.backlinks["n3"] == ["n2"]


class TestWikiNode:
    def test_default_type(self):
        n = WikiNode(id="n1", label="退貨流程")
        assert n.type == "concept"
        assert n.summary == ""
        assert n.source_doc_ids == ()
        assert n.source_chunks == ()

    def test_with_sources(self):
        n = WikiNode(
            id="n1",
            label="退貨流程",
            type="process",
            summary="客戶可於 30 天內申請退貨",
            source_doc_ids=("doc-001", "doc-002"),
            source_chunks=(
                {"doc_id": "doc-001", "chunk_index": 3},
                {"doc_id": "doc-002", "chunk_index": 0},
            ),
        )
        assert n.type == "process"
        assert n.source_doc_ids == ("doc-001", "doc-002")
        assert len(n.source_chunks) == 2


class TestWikiEdge:
    def test_default_confidence_extracted(self):
        e = WikiEdge(id="e1", source="n1", target="n2", relation="requires")
        assert e.confidence == EdgeConfidence.EXTRACTED.value
        assert e.score == 1.0

    def test_inferred_with_score(self):
        e = WikiEdge(
            id="e1",
            source="n1",
            target="n2",
            relation="similar_to",
            confidence=EdgeConfidence.INFERRED.value,
            score=0.78,
        )
        assert e.confidence == "INFERRED"
        assert e.score == 0.78


class TestWikiCluster:
    def test_cluster_with_nodes(self):
        c = WikiCluster(
            id="cluster-001",
            label="退貨相關",
            node_ids=("n1", "n2", "n3"),
            summary="客戶退貨流程相關節點",
        )
        assert c.label == "退貨相關"
        assert len(c.node_ids) == 3


class TestWikiStatus:
    def test_all_status_values(self):
        assert WikiStatus.PENDING.value == "pending"
        assert WikiStatus.COMPILING.value == "compiling"
        assert WikiStatus.READY.value == "ready"
        assert WikiStatus.STALE.value == "stale"
        assert WikiStatus.FAILED.value == "failed"


class TestWikiNodeId:
    def test_generates_unique_id(self):
        id1 = WikiNodeId()
        id2 = WikiNodeId()
        assert id1.value != id2.value

    def test_explicit_value(self):
        vid = WikiNodeId(value="custom-id")
        assert vid.value == "custom-id"
