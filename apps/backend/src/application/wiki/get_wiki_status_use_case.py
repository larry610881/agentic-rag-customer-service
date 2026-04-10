"""GetWikiStatusUseCase — 查詢 bot 的 Wiki Graph 編譯狀態與統計。

新增 Stale Detection（W.4）：
若 wiki graph 是 ready 狀態，但 KB 內最新 document.updated_at >
wiki_graph.compiled_at，會在回傳時自動把 status 降為 'stale'，提示前端
顯示「文件已更新，建議重新編譯」。降級只在 query-time 發生，不寫回 DB。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.knowledge.repository import DocumentRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.wiki.repository import WikiGraphRepository
from src.domain.wiki.value_objects import WikiStatus


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
        document_repository: DocumentRepository,
    ) -> None:
        self._wiki_repo = wiki_graph_repository
        self._doc_repo = document_repository

    async def execute(self, tenant_id: str, bot_id: str) -> WikiStatusView:
        graph = await self._wiki_repo.find_by_bot_id(tenant_id, bot_id)
        if graph is None:
            raise EntityNotFoundError("WikiGraph", f"bot={bot_id}")

        # Stale detection: only downgrade from "ready" to "stale".
        # Other states (compiling/pending/failed) are left unchanged.
        effective_status = graph.status
        if (
            graph.status == WikiStatus.READY.value
            and graph.compiled_at is not None
            and graph.kb_id
        ):
            max_doc_updated_at = await self._doc_repo.find_max_updated_at_by_kb(
                graph.kb_id, tenant_id
            )
            if (
                max_doc_updated_at is not None
                and max_doc_updated_at > graph.compiled_at
            ):
                effective_status = WikiStatus.STALE.value

        meta = graph.metadata or {}
        return WikiStatusView(
            wiki_graph_id=graph.id.value,
            bot_id=graph.bot_id,
            kb_id=graph.kb_id,
            status=effective_status,
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            cluster_count=len(graph.clusters),
            doc_count=int(meta.get("doc_count", 0)),
            compiled_at=graph.compiled_at,
            metadata=meta,
        )
