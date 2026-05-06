"""Delete Chunk Use Case — S-KB-Studio.1（Phase D Outbox 化）

DB delete + 發布 vector.delete outbox 事件，drain worker 接手 Milvus delete。
Chunk 級無 reuse 風險（PK 重用機率 ≈ 0），不設 doc_watermark_ts。

Atomicity 設計：use case 不持有 session（DDD 紅線）。publish session.add 不
commit；後續 doc_repo.delete_chunk 內 atomic commit 帶上 publish 的 INSERT
一起持久化。
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.outbox.events import vector_delete_event
from src.domain.shared.exceptions import EntityNotFoundError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DeleteChunkCommand:
    chunk_id: str
    tenant_id: str
    actor: str = ""


class DeleteChunkUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        kb_repo: KnowledgeBaseRepository,
        publish_outbox_event_use_case: PublishOutboxEventUseCase,
    ) -> None:
        self._doc_repo = document_repo
        self._kb_repo = kb_repo
        self._publish_outbox = publish_outbox_event_use_case

    async def execute(self, command: DeleteChunkCommand) -> None:
        from src.application.knowledge._admin_kb_check import (
            tenant_match_or_admin,
        )
        chunk = await self._doc_repo.find_chunk_by_id(command.chunk_id)
        if chunk is None or not tenant_match_or_admin(
            chunk.tenant_id, command.tenant_id
        ):
            raise EntityNotFoundError("chunk", command.chunk_id)
        doc = await self._doc_repo.find_by_id(chunk.document_id)
        if doc is None or not tenant_match_or_admin(
            doc.tenant_id, command.tenant_id
        ):
            raise EntityNotFoundError("chunk", command.chunk_id)
        kb = await self._kb_repo.find_by_id(doc.kb_id)
        if kb is None or not tenant_match_or_admin(
            kb.tenant_id, command.tenant_id
        ):
            raise EntityNotFoundError("chunk", command.chunk_id)

        # KnowledgeBaseId VO unwrap — 防禦 prod (VO) / test (str) 雙路徑
        kb_id_str = kb.id.value if hasattr(kb.id, "value") else str(kb.id)

        # 1. Publish outbox event（session.add 不 commit）
        # filters={"id": chunk_id} — Milvus chunks 的 PK 是 chunk_id
        collection = f"kb_{kb_id_str}"
        event = vector_delete_event(
            tenant_id=command.tenant_id,
            aggregate_type="chunk",
            aggregate_id=command.chunk_id,
            collection=collection,
            filters={"id": command.chunk_id},
        )
        await self._publish_outbox.execute(event)

        # 2. PG delete chunk — atomic commit 帶上 publish INSERT 一起持久化
        await self._doc_repo.delete_chunk(command.chunk_id)

        logger.info(
            "kb_studio.chunk.delete",
            chunk_id=command.chunk_id,
            kb_id=kb_id_str,
            tenant_id=command.tenant_id,
            actor=command.actor,
            outbox_event_id=event.id,
        )
