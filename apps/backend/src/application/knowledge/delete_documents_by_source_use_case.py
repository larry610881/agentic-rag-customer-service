"""Delete-by-source use case (Issue #44 — External Producer Integration).

Deletes Milvus chunks matching ``(source, source_id IN [...])`` within a
specific knowledge base. Tenant ownership of the KB is validated up front;
no cross-tenant access without system_admin.

Note: this only purges Milvus vectors. The producer is expected to manage
its own document/chunk records (e.g. PMO platform's audit_log table) and
call this endpoint when those records are deleted upstream.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.rag.services import VectorStore

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DeleteDocumentsBySourceCommand:
    kb_id: str
    tenant_id: str  # requester tenant (validated against KB owner)
    source: str
    source_ids: list[str]


class DeleteDocumentsBySourceUseCase:
    def __init__(
        self,
        kb_repo: KnowledgeBaseRepository,
        vector_store: VectorStore,
    ) -> None:
        self._kb_repo = kb_repo
        self._vs = vector_store

    async def execute(self, command: DeleteDocumentsBySourceCommand) -> None:
        # ensure_kb_accessible raises EntityNotFoundError on missing KB OR
        # cross-tenant non-admin access (uniform 404 to prevent enumeration).
        kb, effective_tenant_id = await ensure_kb_accessible(
            self._kb_repo, command.kb_id, command.tenant_id
        )

        kb_id_str = kb.id.value if hasattr(kb.id, "value") else str(kb.id)
        collection = f"kb_{kb_id_str}"

        # tenant_id filter is mandatory — even after KB ownership check we
        # never want to issue a cross-tenant delete in case admin is operating
        # against the wrong collection.
        await self._vs.delete(
            collection=collection,
            filters={
                "tenant_id": effective_tenant_id,
                "source": command.source,
                "source_id": command.source_ids,
            },
        )

        logger.info(
            "kb.documents.delete_by_source",
            kb_id=kb_id_str,
            tenant_id=effective_tenant_id,
            source=command.source,
            source_id_count=len(command.source_ids),
        )
