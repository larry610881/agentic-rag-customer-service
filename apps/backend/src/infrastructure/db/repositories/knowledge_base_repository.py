from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.knowledge.value_objects import KnowledgeBaseId
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
        await self._session.commit()

    async def find_by_id(self, kb_id: str) -> KnowledgeBase | None:
        stmt = select(KnowledgeBaseModel).where(KnowledgeBaseModel.id == kb_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

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
