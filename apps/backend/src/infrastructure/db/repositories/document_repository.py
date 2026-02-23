from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.knowledge.entity import Document
from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.value_objects import DocumentId
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
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, document: Document) -> None:
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
        await self._session.commit()

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

    async def update_status(
        self, doc_id: str, status: str, chunk_count: int | None = None
    ) -> None:
        values: dict = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id == doc_id)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.commit()
