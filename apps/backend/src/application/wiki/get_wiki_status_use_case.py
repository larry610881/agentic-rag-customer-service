"""GetWikiStatusUseCase — 查詢 bot 的 Wiki Graph 編譯狀態與統計。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.wiki.repository import WikiGraphRepository


@dataclass(frozen=True)
class WikiStatusView:
    """Wiki status 查詢結果 — 給 router 組 response 用。"""

    wiki_graph_id: str
    bot_id: str
    kb_id: str
    status: str
    node_count: int
    edge_count: int
    cluster_count: int
    doc_count: int
    compiled_at: datetime | None
    metadata: dict


class GetWikiStatusUseCase:
    def __init__(
        self,
        wiki_graph_repository: WikiGraphRepository,
    ) -> None:
        self._wiki_repo = wiki_graph_repository

    async def execute(self, tenant_id: str, bot_id: str) -> WikiStatusView:
        graph = await self._wiki_repo.find_by_bot_id(tenant_id, bot_id)
        if graph is None:
            raise EntityNotFoundError("WikiGraph", f"bot={bot_id}")

        meta = graph.metadata or {}
        return WikiStatusView(
            wiki_graph_id=graph.id.value,
            bot_id=graph.bot_id,
            kb_id=graph.kb_id,
            status=graph.status,
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            cluster_count=len(graph.clusters),
            doc_count=int(meta.get("doc_count", 0)),
            compiled_at=graph.compiled_at,
            metadata=meta,
        )
