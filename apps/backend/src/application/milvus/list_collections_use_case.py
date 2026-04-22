"""List Milvus Collections Use Case — S-KB-Studio.1"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.services import VectorStore


@dataclass(frozen=True)
class ListCollectionsQuery:
    role: str  # "system_admin" | "tenant_admin"
    tenant_id: str | None = None


@dataclass
class CollectionInfo:
    name: str
    row_count: int = 0
    indexes: list[dict[str, Any]] = field(default_factory=list)


class ListCollectionsUseCase:
    def __init__(
        self,
        vector_store: VectorStore,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self._vs = vector_store
        self._kb_repo = kb_repo

    async def execute(
        self, query: ListCollectionsQuery
    ) -> list[CollectionInfo]:
        raw = await self._vs.list_collections()
        all_cols: list[CollectionInfo] = []
        for item in raw:
            stats = await self._vs.get_collection_stats(item["name"])
            all_cols.append(
                CollectionInfo(
                    name=item["name"],
                    row_count=item.get("row_count", stats.get("row_count", 0)),
                    indexes=stats.get("indexes", []),
                )
            )

        if query.role == "system_admin":
            return all_cols

        # tenant_admin：只看自己 KB 的 kb_* collection
        if query.tenant_id is None:
            return []
        kbs = await self._kb_repo.find_all_by_tenant(query.tenant_id)
        allowed = {f"kb_{kb.id}" for kb in kbs}
        return [c for c in all_cols if c.name in allowed]
