"""Update Chunk Use Case — S-KB-Studio.1

驗證 tenant chain（chunk→doc→kb→tenant_id），更新 DB，並 enqueue reembed_chunk job。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import EntityNotFoundError

if TYPE_CHECKING:
    from arq import ArqRedis

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class UpdateChunkCommand:
    chunk_id: str
    tenant_id: str  # from JWT
    content: str | None = None
    context_text: str | None = None
    actor: str = ""


class UpdateChunkUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        kb_repo: KnowledgeBaseRepository,
        arq_pool: "ArqRedis | None" = None,
    ) -> None:
        self._doc_repo = document_repo
        self._kb_repo = kb_repo
        self._arq = arq_pool

    async def execute(self, command: UpdateChunkCommand) -> None:
        # 紅線：tenant chain 驗證 (chunk -> doc -> kb -> tenant)
        chunk = await self._doc_repo.find_chunk_by_id(command.chunk_id)
        if chunk is None:
            raise EntityNotFoundError("chunk", command.chunk_id)
        # chunk 自帶 tenant_id，先擋；再驗 kb 層以防 entity mutation
        if chunk.tenant_id != command.tenant_id:
            raise EntityNotFoundError("chunk", command.chunk_id)
        doc = await self._doc_repo.find_by_id(chunk.document_id)
        if doc is None or doc.tenant_id != command.tenant_id:
            raise EntityNotFoundError("chunk", command.chunk_id)
        kb = await self._kb_repo.find_by_id(doc.kb_id)
        if kb is None or kb.tenant_id != command.tenant_id:
            raise EntityNotFoundError("chunk", command.chunk_id)

        if command.content is not None and not command.content.strip():
            raise ValueError("content must not be empty")
        if command.content is None and command.context_text is None:
            raise ValueError("at least one of content / context_text required")

        content_diff_len = 0
        if command.content is not None:
            content_diff_len = abs(len(command.content) - len(chunk.content))

        await self._doc_repo.update_chunk(
            command.chunk_id,
            content=command.content,
            context_text=command.context_text,
        )

        # enqueue re-embed job (若 arq pool 可用)
        if self._arq is not None:
            await self._arq.enqueue_job("reembed_chunk", command.chunk_id)

        logger.info(
            "kb_studio.chunk.update",
            chunk_id=command.chunk_id,
            kb_id=kb.id,
            tenant_id=command.tenant_id,
            actor=command.actor,
            content_diff_len=content_diff_len,
        )
