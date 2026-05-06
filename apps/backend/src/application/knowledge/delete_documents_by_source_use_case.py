"""Delete-by-source use case (Phase C — 透過 Outbox Pattern)

Issue #44 — External Producer Integration。Producer (e.g. PMO 平台 audit_log)
刪掉 upstream 紀錄時 cascade 清掉 RAG Milvus 對應的 chunks。

Phase C 改寫：vector_store.delete 直接呼叫 → publish vector.delete outbox event。
不設 doc_watermark_ts — source-driven 是「按 source/source_id 過濾刪一批 chunks」，
不對應單一 doc，watermark guard 不適用（producer 短時間 re-upload 同 source_id
有理論 race 風險，由 producer side 自行避免；本 sprint 範圍不處理）。

Tenant ownership of the KB is validated up front; no cross-tenant access
without system_admin.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.outbox.events import vector_delete_event

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
        publish_outbox_event_use_case: PublishOutboxEventUseCase,
    ) -> None:
        self._kb_repo = kb_repo
        self._publish_outbox = publish_outbox_event_use_case

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
        event = vector_delete_event(
            tenant_id=effective_tenant_id,
            aggregate_type="document_source",
            aggregate_id=f"{command.source}:{kb_id_str}",
            collection=collection,
            filters={
                "tenant_id": effective_tenant_id,
                "source": command.source,
                "source_id": command.source_ids,
            },
            # 不帶 watermark — source-driven 無單一 doc.created_at 可比
            doc_watermark_ts=None,
        )
        await self._publish_outbox.execute(event)

        logger.info(
            "kb.documents.delete_by_source.outbox_published",
            kb_id=kb_id_str,
            tenant_id=effective_tenant_id,
            source=command.source,
            source_id_count=len(command.source_ids),
            event_id=event.id,
        )
