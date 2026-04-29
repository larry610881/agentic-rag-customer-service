"""Delete Chunk Use Case — S-KB-Studio.1

DB delete + Milvus delete（雙階段，Milvus 失敗不擋 DB，只 log warning）。
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.rag.services import VectorStore
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
        vector_store: VectorStore,
    ) -> None:
        self._doc_repo = document_repo
        self._kb_repo = kb_repo
        self._vs = vector_store

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

        # 1. DB delete 優先
        await self._doc_repo.delete_chunk(command.chunk_id)

        # 2. Milvus delete 容錯
        collection = f"kb_{kb_id_str}"
        try:
            await self._vs.delete(
                collection=collection,
                filters={"id": command.chunk_id},
            )
        except Exception:
            logger.warning(
                "chunk.delete.milvus_failed",
                chunk_id=command.chunk_id,
                collection=collection,
                exc_info=True,
            )

        logger.info(
            "kb_studio.chunk.delete",
            chunk_id=command.chunk_id,
            kb_id=kb_id_str,
            tenant_id=command.tenant_id,
            actor=command.actor,
        )
