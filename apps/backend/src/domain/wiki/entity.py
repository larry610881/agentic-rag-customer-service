"""Wiki BC domain entities.

WikiGraph 是 Wiki BC 聚合根，內含 WikiNode/WikiEdge/WikiCluster 內部 VO。
JSONB 儲存結構：
    nodes:     dict[node_id, {label, type, summary, source_doc_ids, source_chunks}]
    edges:     dict[edge_id, {source, target, relation, confidence, score}]
    backlinks: dict[target_node_id, list[source_node_id]]
    clusters:  list[{id, label, node_ids, summary}]
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.wiki.value_objects import WikiGraphId, WikiStatus


@dataclass(frozen=True)
class WikiNode:
    """Wiki 節點 — Value Object。

    代表從文件中擷取的一個概念 / 實體 / 流程 / 政策節點。
    """

    id: str
    label: str
    type: str = "concept"  # concept | entity | process | policy
    summary: str = ""
    source_doc_ids: tuple[str, ...] = ()
    source_chunks: tuple[dict, ...] = ()


@dataclass(frozen=True)
class WikiEdge:
    """Wiki 關係邊 — Value Object。

    source/target 指向 WikiNode.id，relation 為語意關係字串（requires 等）。
    confidence 遵循 EdgeConfidence enum：EXTRACTED / INFERRED / AMBIGUOUS。
    """

    id: str
    source: str
    target: str
    relation: str
    confidence: str = "EXTRACTED"  # EdgeConfidence value
    score: float = 1.0


@dataclass(frozen=True)
class WikiCluster:
    """Wiki 集群 — Value Object。

    Leiden community detection 產出的節點群組，帶有一個摘要標籤。
    """

    id: str
    label: str
    node_ids: tuple[str, ...] = ()
    summary: str = ""


@dataclass
class WikiGraph:
    """Wiki Graph 聚合根。

    一個 bot 對應一個 WikiGraph（1:1）。
    nodes/edges/backlinks/clusters 都儲存於 JSONB 欄位。
    tenant_id 冗餘儲存，便於多租戶隔離查詢。
    """

    id: WikiGraphId = field(default_factory=WikiGraphId)
    tenant_id: str = ""
    bot_id: str = ""
    kb_id: str = ""
    status: str = WikiStatus.PENDING.value
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[str, dict] = field(default_factory=dict)
    backlinks: dict[str, list[str]] = field(default_factory=dict)
    clusters: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    compiled_at: datetime | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)
