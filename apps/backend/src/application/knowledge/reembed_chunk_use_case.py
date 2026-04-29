"""ReEmbed Chunk Use Case — S-KB-Studio.1 (arq job handler)

單 chunk 重新向量化：查 chunk → 組 embed 文本 → embed → Milvus upsert_single
→ RecordUsage（embedding）。失敗不 retry（log 後由人工處理）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.rag.services import EmbeddingService, VectorStore
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import UsageCategory

if TYPE_CHECKING:
    from src.application.usage.record_usage_use_case import RecordUsageUseCase

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ReEmbedChunkCommand:
    chunk_id: str
    actor: str = "worker:reembed_chunk"


class ReEmbedChunkUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        kb_repo: KnowledgeBaseRepository,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        record_usage: "RecordUsageUseCase | None" = None,
    ) -> None:
        self._doc_repo = document_repo
        self._kb_repo = kb_repo
        self._embed = embedding_service
        self._vs = vector_store
        self._record_usage = record_usage

    async def execute(self, command: ReEmbedChunkCommand) -> None:
        chunk = await self._doc_repo.find_chunk_by_id(command.chunk_id)
        if chunk is None:
            logger.warning(
                "chunk.reembed.not_found", chunk_id=command.chunk_id
            )
            return
        doc = await self._doc_repo.find_by_id(chunk.document_id)
        if doc is None:
            logger.warning(
                "chunk.reembed.doc_not_found",
                chunk_id=command.chunk_id,
                document_id=chunk.document_id,
            )
            return
        kb = await self._kb_repo.find_by_id(doc.kb_id)
        if kb is None:
            logger.warning(
                "chunk.reembed.kb_not_found",
                chunk_id=command.chunk_id,
                kb_id=doc.kb_id,
            )
            return

        embed_text = (
            f"{chunk.context_text}\n\n{chunk.content}"
            if chunk.context_text
            else chunk.content
        )
        try:
            vectors = await self._embed.embed_texts([embed_text])
        except Exception:
            logger.error(
                "chunk.reembed.embedding_failed",
                chunk_id=command.chunk_id,
                exc_info=True,
            )
            return

        vector = vectors[0]
        # Milvus payload 必含 tenant_id（安全紅線）
        # KnowledgeBaseId VO unwrap — 防禦 prod (VO) / test (str) 雙路徑
        kb_id_str = kb.id.value if hasattr(kb.id, "value") else str(kb.id)

        payload = {
            "tenant_id": chunk.tenant_id,
            "document_id": chunk.document_id,
            "content": chunk.content,
            "chunk_index": chunk.chunk_index,
            "context_text": chunk.context_text,
            "category_id": chunk.category_id,
        }
        await self._vs.upsert_single(
            collection=f"kb_{kb_id_str}",
            id=command.chunk_id,
            vector=vector,
            payload=payload,
        )

        # Record embedding token usage (單 chunk 只算該筆 input token 數約略)
        if self._record_usage is not None:
            # embedding 只有 input token，無 output / cache
            usage = TokenUsage(
                model=getattr(self._embed, "model_name", "embedding"),
                input_tokens=len(embed_text),  # 簡估；實際由 service 回傳 tokens 更準
                output_tokens=0,
                estimated_cost=0.0,
            )
            try:
                await self._record_usage.execute(
                    tenant_id=chunk.tenant_id,
                    request_type=UsageCategory.EMBEDDING.value,
                    usage=usage,
                    kb_id=kb_id_str,
                )
            except Exception:
                logger.warning(
                    "chunk.reembed.record_usage_failed",
                    chunk_id=command.chunk_id,
                    exc_info=True,
                )

        logger.info(
            "kb_studio.chunk.reembed",
            chunk_id=command.chunk_id,
            kb_id=kb_id_str,
            tenant_id=chunk.tenant_id,
            actor=command.actor,
        )
