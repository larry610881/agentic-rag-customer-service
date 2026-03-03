from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.knowledge.entity import Chunk, Document
from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.value_objects import ChunkId, DocumentId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.chunk_model import ChunkModel
from src.infrastructure.db.models.document_model import DocumentModel


class SQLAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: DocumentModel) -> Document:
        return Document(
            id=DocumentId(value=model.id),
            kb_id=model.kb_id,
            tenant_id=model.tenant_id,
            filename=model.filename,
            content_type=model.content_type,
            content=model.content,
            status=model.status,
            chunk_count=model.chunk_count,
            avg_chunk_length=model.avg_chunk_length,
            min_chunk_length=model.min_chunk_length,
            max_chunk_length=model.max_chunk_length,
            quality_score=model.quality_score,
            quality_issues=(
                model.quality_issues.split(",") if model.quality_issues else []
            ),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _chunk_to_entity(self, model: ChunkModel) -> Chunk:
        return Chunk(
            id=ChunkId(value=model.id),
            document_id=model.document_id,
            tenant_id=model.tenant_id,
            content=model.content,
            chunk_index=model.chunk_index,
            metadata=model.metadata_ or {},
        )

    # --- Document write methods ---

    async def save(self, document: Document) -> None:
        async with atomic(self._session):
            model = DocumentModel(
                id=document.id.value,
                kb_id=document.kb_id,
                tenant_id=document.tenant_id,
                filename=document.filename,
                content_type=document.content_type,
                content=document.content,
                status=document.status,
                chunk_count=document.chunk_count,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            self._session.add(model)

    async def delete(self, doc_id: str) -> None:
        async with atomic(self._session):
            # Delete chunks first (aggregate internal Entity)
            await self._session.execute(
                delete(ChunkModel).where(ChunkModel.document_id == doc_id)
            )
            # Then delete the aggregate root
            await self._session.execute(
                delete(DocumentModel).where(DocumentModel.id == doc_id)
            )

    async def update_status(
        self, doc_id: str, status: str, chunk_count: int | None = None
    ) -> None:
        values: dict = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        async with atomic(self._session):
            stmt = (
                update(DocumentModel)
                .where(DocumentModel.id == doc_id)
                .values(**values)
            )
            await self._session.execute(stmt)

    async def update_quality(
        self,
        doc_id: str,
        quality_score: float,
        avg_chunk_length: int,
        min_chunk_length: int,
        max_chunk_length: int,
        quality_issues: list[str],
    ) -> None:
        async with atomic(self._session):
            stmt = (
                update(DocumentModel)
                .where(DocumentModel.id == doc_id)
                .values(
                    quality_score=quality_score,
                    avg_chunk_length=avg_chunk_length,
                    min_chunk_length=min_chunk_length,
                    max_chunk_length=max_chunk_length,
                    quality_issues=",".join(quality_issues),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self._session.execute(stmt)

    # --- Document read methods ---

    async def find_by_id(self, doc_id: str) -> Document | None:
        stmt = select(DocumentModel).where(DocumentModel.id == doc_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_all_by_kb(self, kb_id: str) -> list[Document]:
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.kb_id == kb_id)
            .order_by(DocumentModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    # --- Chunk write methods (aggregate internal Entity) ---

    async def save_chunks(self, chunks: list[Chunk]) -> None:
        async with atomic(self._session):
            models = [
                ChunkModel(
                    id=c.id.value,
                    document_id=c.document_id,
                    tenant_id=c.tenant_id,
                    content=c.content,
                    chunk_index=c.chunk_index,
                    metadata_=c.metadata,
                )
                for c in chunks
            ]
            self._session.add_all(models)

    async def delete_chunks_by_document(self, document_id: str) -> None:
        async with atomic(self._session):
            stmt = delete(ChunkModel).where(ChunkModel.document_id == document_id)
            await self._session.execute(stmt)

    # --- Chunk read methods ---

    async def find_chunks_by_document_paginated(
        self, document_id: str, limit: int = 20, offset: int = 0
    ) -> list[Chunk]:
        stmt = (
            select(ChunkModel)
            .where(ChunkModel.document_id == document_id)
            .order_by(ChunkModel.chunk_index)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._chunk_to_entity(m) for m in result.scalars().all()]

    async def count_chunks_by_document(self, document_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(ChunkModel)
            .where(ChunkModel.document_id == document_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def find_chunk_ids_by_kb(
        self, kb_id: str
    ) -> dict[str, list[str]]:
        stmt = (
            select(ChunkModel.id, ChunkModel.document_id)
            .join(DocumentModel, ChunkModel.document_id == DocumentModel.id)
            .where(DocumentModel.kb_id == kb_id)
        )
        result = await self._session.execute(stmt)
        mapping: dict[str, list[str]] = defaultdict(list)
        for chunk_id, doc_id in result.all():
            mapping[doc_id].append(chunk_id)
        return dict(mapping)
