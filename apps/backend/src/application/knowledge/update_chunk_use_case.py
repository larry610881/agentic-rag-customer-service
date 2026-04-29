"""Update Chunk Use Case — S-KB-Studio.1

驗證 tenant chain（chunk→doc→kb→tenant_id），更新 DB，並 enqueue reembed_chunk job。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

import structlog

from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import EntityNotFoundError

# 簽名: enqueue(job_name, chunk_id) -> awaitable[str | None]
EnqueueFunc = Callable[..., Awaitable[str | None]]

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
        arq_pool: object | None = None,  # arq.ArqRedis or fake with enqueue_job
        enqueue_fn: EnqueueFunc | None = None,
    ) -> None:
        self._doc_repo = document_repo
        self._kb_repo = kb_repo
        self._arq = arq_pool
        self._enqueue_fn = enqueue_fn

    async def execute(self, command: UpdateChunkCommand) -> None:
        # 紅線：tenant chain 驗證 (chunk -> doc -> kb -> tenant)
        chunk = await self._doc_repo.find_chunk_by_id(command.chunk_id)
        from src.application.knowledge._admin_kb_check import (
            tenant_match_or_admin,
        )
        if chunk is None:
            raise EntityNotFoundError("chunk", command.chunk_id)
        # chunk 自帶 tenant_id，先擋；再驗 kb 層以防 entity mutation
        # system_admin (SYSTEM_TENANT_ID) bypass — 用 tenant_match_or_admin
        if not tenant_match_or_admin(chunk.tenant_id, command.tenant_id):
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

        # enqueue re-embed job — 兩條路徑都支援
        # 1. arq_pool（測試用 FakeArqPool 注入）
        # 2. enqueue_fn（生產用 infrastructure.queue.arq_pool.enqueue 注入）
        if self._arq is not None:
            await self._arq.enqueue_job("reembed_chunk", command.chunk_id)
        elif self._enqueue_fn is not None:
            await self._enqueue_fn("reembed_chunk", command.chunk_id)

        # KnowledgeBaseId VO unwrap — 防禦 prod (VO) / test (str) 雙路徑
        kb_id_str = kb.id.value if hasattr(kb.id, "value") else str(kb.id)
        logger.info(
            "kb_studio.chunk.update",
            chunk_id=command.chunk_id,
            kb_id=kb_id_str,
            tenant_id=command.tenant_id,
            actor=command.actor,
            content_diff_len=content_diff_len,
        )
