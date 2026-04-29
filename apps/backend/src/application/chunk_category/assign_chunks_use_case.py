"""Assign Chunks To Category Use Case — S-KB-Studio.1"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from src.domain.knowledge.repository import (
    ChunkCategoryRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import EntityNotFoundError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AssignChunksCommand:
    kb_id: str
    category_id: str
    tenant_id: str
    chunk_ids: list[str]
    actor: str = ""


class AssignChunksUseCase:
    def __init__(
        self,
        category_repo: ChunkCategoryRepository,
        document_repo: DocumentRepository,
        kb_repo: KnowledgeBaseRepository,
    ) -> None:
        self._cat_repo = category_repo
        self._doc_repo = document_repo
        self._kb_repo = kb_repo

    async def execute(self, command: AssignChunksCommand) -> int:
        """回傳實際 assign 的 chunk 數（全部 chunks 必須屬於該租戶的該 KB）。"""
        from src.application.knowledge._admin_kb_check import ensure_kb_accessible
        kb, _ = await ensure_kb_accessible(
            self._kb_repo, command.kb_id, command.tenant_id
        )

        category = await self._cat_repo.find_by_id(command.category_id)
        if category is None or category.kb_id != command.kb_id:
            raise EntityNotFoundError("category", command.category_id)
        if not command.chunk_ids:
            return 0

        # 驗每個 chunk 屬於該 kb + tenant 才放進 batch
        verified_ids: list[str] = []
        for cid in command.chunk_ids:
            chunk = await self._doc_repo.find_chunk_by_id(cid)
            if chunk is None or chunk.tenant_id != command.tenant_id:
                continue
            doc = await self._doc_repo.find_by_id(chunk.document_id)
            if doc is None or doc.kb_id != command.kb_id:
                continue
            verified_ids.append(cid)

        if verified_ids:
            await self._cat_repo.assign_chunks(
                command.category_id, verified_ids
            )

        logger.info(
            "kb_studio.category.assign",
            cat_id=command.category_id,
            kb_id=command.kb_id,
            chunk_count=len(verified_ids),
            actor=command.actor,
        )
        return len(verified_ids)
