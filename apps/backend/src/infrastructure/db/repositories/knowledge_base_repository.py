from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.chunk_model import ChunkModel
from src.infrastructure.db.models.document_model import DocumentModel
from src.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel


class SQLAlchemyKnowledgeBaseRepository(KnowledgeBaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(
        model: KnowledgeBaseModel, document_count: int = 0
    ) -> KnowledgeBase:
        return KnowledgeBase(
            id=KnowledgeBaseId(value=model.id),
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            kb_type=model.kb_type,
            ocr_mode=model.ocr_mode,
            document_count=document_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _doc_count_subquery():
        return (
            select(
                DocumentModel.kb_id,
                func.count().label("doc_count"),
            )
            .group_by(DocumentModel.kb_id)
            .subquery()
        )

    async def save(self, knowledge_base: KnowledgeBase) -> None:
        async with atomic(self._session):
            model = KnowledgeBaseModel(
                id=knowledge_base.id.value,
                tenant_id=knowledge_base.tenant_id,
                name=knowledge_base.name,
                description=knowledge_base.description,
                kb_type=knowledge_base.kb_type,
                ocr_mode=knowledge_base.ocr_mode,
                created_at=knowledge_base.created_at,
                updated_at=knowledge_base.updated_at,
            )
            self._session.add(model)

    async def find_by_id(self, kb_id: str) -> KnowledgeBase | None:
        doc_sub = self._doc_count_subquery()
        stmt = (
            select(
                KnowledgeBaseModel,
                func.coalesce(doc_sub.c.doc_count, 0),
            )
            .outerjoin(doc_sub, KnowledgeBaseModel.id == doc_sub.c.kb_id)
            .where(KnowledgeBaseModel.id == kb_id)
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return self._to_entity(row[0], int(row[1]))

    async def find_all(
        self,
        *,
        tenant_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[KnowledgeBase]:
        doc_sub = self._doc_count_subquery()
        stmt = (
            select(
                KnowledgeBaseModel,
                func.coalesce(doc_sub.c.doc_count, 0),
            )
            .outerjoin(doc_sub, KnowledgeBaseModel.id == doc_sub.c.kb_id)
            .order_by(KnowledgeBaseModel.created_at)
        )
        if tenant_id is not None:
            stmt = stmt.where(KnowledgeBaseModel.tenant_id == tenant_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(row[0], int(row[1])) for row in result.all()]

    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[KnowledgeBase]:
        doc_sub = self._doc_count_subquery()
        stmt = (
            select(
                KnowledgeBaseModel,
                func.coalesce(doc_sub.c.doc_count, 0),
            )
            .outerjoin(doc_sub, KnowledgeBaseModel.id == doc_sub.c.kb_id)
            .where(
                KnowledgeBaseModel.tenant_id == tenant_id,
                KnowledgeBaseModel.kb_type == "user",
            )
            .order_by(KnowledgeBaseModel.created_at)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(row[0], int(row[1])) for row in result.all()]

    async def count_by_tenant(self, tenant_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(KnowledgeBaseModel)
            .where(
                KnowledgeBaseModel.tenant_id == tenant_id,
                KnowledgeBaseModel.kb_type == "user",
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_all(self, *, tenant_id: str | None = None) -> int:
        stmt = select(func.count()).select_from(KnowledgeBaseModel)
        if tenant_id is not None:
            stmt = stmt.where(KnowledgeBaseModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def find_system_kbs(self, tenant_id: str) -> list[KnowledgeBase]:
        doc_sub = self._doc_count_subquery()
        stmt = (
            select(
                KnowledgeBaseModel,
                func.coalesce(doc_sub.c.doc_count, 0),
            )
            .outerjoin(doc_sub, KnowledgeBaseModel.id == doc_sub.c.kb_id)
            .where(
                KnowledgeBaseModel.tenant_id == tenant_id,
                KnowledgeBaseModel.kb_type == "system",
            )
            .order_by(KnowledgeBaseModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row[0], int(row[1])) for row in result.all()]

    async def delete(self, kb_id: str) -> None:
        async with atomic(self._session):
            # 1) 取得該 KB 下所有 document id
            doc_ids_result = await self._session.execute(
                select(DocumentModel.id).where(DocumentModel.kb_id == kb_id)
            )
            doc_ids = [row[0] for row in doc_ids_result.all()]

            # 2) 刪除 chunks（屬於這些 documents）
            if doc_ids:
                await self._session.execute(
                    delete(ChunkModel).where(
                        ChunkModel.document_id.in_(doc_ids)
                    )
                )

            # 3) 刪除 documents
            await self._session.execute(
                delete(DocumentModel).where(DocumentModel.kb_id == kb_id)
            )

            # 4) 刪除 knowledge_base
            await self._session.execute(
                delete(KnowledgeBaseModel).where(
                    KnowledgeBaseModel.id == kb_id
                )
            )
