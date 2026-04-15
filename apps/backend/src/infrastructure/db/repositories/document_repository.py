from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

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
            raw_content=model.raw_content or b"" if "raw_content" not in sa_inspect(model).unloaded else b"",
            storage_path=model.storage_path if "storage_path" not in sa_inspect(model).unloaded else "",
            status=model.status,
            parent_id=model.parent_id,
            page_number=model.page_number,
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
            context_text=model.context_text or "",
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
                raw_content=document.raw_content or None,
                storage_path=document.storage_path,
                status=document.status,
                parent_id=document.parent_id,
                page_number=document.page_number,
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

    async def update_storage_path(
        self, doc_id: str, storage_path: str
    ) -> None:
        async with atomic(self._session):
            stmt = (
                update(DocumentModel)
                .where(DocumentModel.id == doc_id)
                .values(
                    storage_path=storage_path,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self._session.execute(stmt)

    async def update_content(
        self, doc_id: str, content: str
    ) -> None:
        async with atomic(self._session):
            stmt = (
                update(DocumentModel)
                .where(DocumentModel.id == doc_id)
                .values(
                    content=content,
                    updated_at=datetime.now(timezone.utc),
                )
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

    async def find_all_by_kb(
        self,
        kb_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Document]:
        stmt = (
            select(DocumentModel)
            .options(defer(DocumentModel.raw_content))
            .where(DocumentModel.kb_id == kb_id)
            .order_by(DocumentModel.created_at)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_children(self, parent_id: str) -> list[Document]:
        stmt = (
            select(DocumentModel)
            .options(defer(DocumentModel.raw_content))
            .where(DocumentModel.parent_id == parent_id)
            .order_by(DocumentModel.page_number)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_children_by_status(self, parent_id: str) -> dict[str, int]:
        stmt = (
            select(DocumentModel.status, func.count())
            .where(DocumentModel.parent_id == parent_id)
            .group_by(DocumentModel.status)
        )
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def count_by_kb(self, kb_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentModel)
            .where(DocumentModel.kb_id == kb_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # --- Chunk write methods (aggregate internal Entity) ---

    async def save_chunks(self, chunks: list[Chunk]) -> None:
        async with atomic(self._session):
            models = [
                ChunkModel(
                    id=c.id.value,
                    document_id=c.document_id,
                    tenant_id=c.tenant_id,
                    content=c.content,
                    context_text=c.context_text,
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

    async def update_chunks_category(
        self, chunk_ids: list[str], category_id: str | None
    ) -> None:
        if not chunk_ids:
            return
        from sqlalchemy import update
        async with atomic(self._session):
            await self._session.execute(
                update(ChunkModel)
                .where(ChunkModel.id.in_(chunk_ids))
                .values(category_id=category_id)
            )

    async def find_chunks_by_category(
        self, category_id: str
    ) -> list[Chunk]:
        stmt = (
            select(ChunkModel)
            .where(ChunkModel.category_id == category_id)
            .order_by(ChunkModel.chunk_index)
        )
        result = await self._session.execute(stmt)
        return [self._chunk_to_entity(m) for m in result.scalars().all()]

    async def find_max_updated_at_by_kb(
        self, kb_id: str, tenant_id: str
    ) -> datetime | None:
        """Return MAX(documents.updated_at) for stale detection."""
        stmt = (
            select(func.max(DocumentModel.updated_at))
            .where(
                DocumentModel.kb_id == kb_id,
                DocumentModel.tenant_id == tenant_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
