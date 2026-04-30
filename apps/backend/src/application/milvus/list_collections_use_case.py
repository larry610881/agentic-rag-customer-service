"""List Milvus Collections Use Case — S-KB-Studio.1.

v2 (2026-04-29)：
- 額外回傳 kb_id / kb_name / tenant_id / tenant_name（admin UI 別只看 GUID）
- conv_summaries 等非 kb_* collection 這些欄位為 None
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.services import VectorStore
from src.domain.tenant.repository import TenantRepository


@dataclass(frozen=True)
class ListCollectionsQuery:
    role: str  # "system_admin" | "tenant_admin"
    tenant_id: str | None = None


@dataclass
class CollectionInfo:
    name: str
    row_count: int = 0
    indexes: list[dict[str, Any]] = field(default_factory=list)
    # 顯示用 — admin 不可能用 GUID 找 KB
    kb_id: str | None = None
    kb_name: str | None = None
    tenant_id: str | None = None
    tenant_name: str | None = None


def _collection_to_kb_id(name: str) -> str | None:
    """Convert Milvus collection name to KB UUID.

    `kb_xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx`
    → `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
    """
    if not name.startswith("kb_"):
        return None
    raw = name[3:]
    # Milvus collection 命名 `_` 取代 `-`，UUID 一定 5 段
    parts = raw.split("_")
    if len(parts) != 5:
        return None
    return "-".join(parts)


class ListCollectionsUseCase:
    def __init__(
        self,
        vector_store: VectorStore,
        kb_repo: KnowledgeBaseRepository,
        tenant_repo: TenantRepository | None = None,
    ) -> None:
        self._vs = vector_store
        self._kb_repo = kb_repo
        self._tenant_repo = tenant_repo

    async def execute(
        self, query: ListCollectionsQuery
    ) -> list[CollectionInfo]:
        raw = await self._vs.list_collections()
        all_cols: list[CollectionInfo] = []
        # 預先 cache 已查過的 tenant 避免重複 query
        tenant_cache: dict[str, str] = {}

        for item in raw:
            stats = await self._vs.get_collection_stats(item["name"])
            kb_id = _collection_to_kb_id(item["name"])
            kb_name = None
            tenant_id = None
            tenant_name = None
            if kb_id:
                try:
                    kb = await self._kb_repo.find_by_id(kb_id)
                    if kb:
                        kb_name = kb.name
                        tenant_id = kb.tenant_id
                        if self._tenant_repo and tenant_id:
                            if tenant_id not in tenant_cache:
                                t = await self._tenant_repo.find_by_id(
                                    tenant_id
                                )
                                tenant_cache[tenant_id] = t.name if t else ""
                            tenant_name = tenant_cache[tenant_id] or None
                except Exception:
                    pass  # display fallback to GUID — 不擋功能
            all_cols.append(
                CollectionInfo(
                    name=item["name"],
                    row_count=item.get(
                        "row_count", stats.get("row_count", 0)
                    ),
                    indexes=stats.get("indexes", []),
                    kb_id=kb_id,
                    kb_name=kb_name,
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                )
            )

        if query.role == "system_admin":
            return all_cols

        # tenant_admin：只看自己 KB 的 kb_* collection
        if query.tenant_id is None:
            return []
        kbs = await self._kb_repo.find_all_by_tenant(query.tenant_id)
        # kb.id 是 KnowledgeBaseId VO → 必須 unwrap .value 才能 match
        # 之前 f"kb_{kb.id}" 會輸出 "kb_KnowledgeBaseId(value='...')" → 永遠 mismatch
        # 結果：tenant_admin 看 Milvus 管理頁是空清單
        allowed = {
            f"kb_{kb.id.value if hasattr(kb.id, 'value') else kb.id}"
            for kb in kbs
        }
        return [c for c in all_cols if c.name in allowed]
