from sqlalchemy import delete, select
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

    def _to_entity(self, model: KnowledgeBaseModel) -> KnowledgeBase:
        return KnowledgeBase(
            id=KnowledgeBaseId(value=model.id),
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            kb_type=model.kb_type,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, knowledge_base: KnowledgeBase) -> None:
        async with atomic(self._session):
            model = KnowledgeBaseModel(
                id=knowledge_base.id.value,
                tenant_id=knowledge_base.tenant_id,
                name=knowledge_base.name,
                description=knowledge_base.description,
                kb_type=knowledge_base.kb_type,
                created_at=knowledge_base.created_at,
                updated_at=knowledge_base.updated_at,
            )
            self._session.add(model)

    async def find_by_id(self, kb_id: str) -> KnowledgeBase | None:
        stmt = select(KnowledgeBaseModel).where(KnowledgeBaseModel.id == kb_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_all(self) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBaseModel)
            .order_by(KnowledgeBaseModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_all_by_tenant(self, tenant_id: str) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBaseModel)
            .where(
                KnowledgeBaseModel.tenant_id == tenant_id,
                KnowledgeBaseModel.kb_type == "user",
            )
            .order_by(KnowledgeBaseModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_system_kbs(self, tenant_id: str) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBaseModel)
            .where(
                KnowledgeBaseModel.tenant_id == tenant_id,
                KnowledgeBaseModel.kb_type == "system",
            )
            .order_by(KnowledgeBaseModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

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
