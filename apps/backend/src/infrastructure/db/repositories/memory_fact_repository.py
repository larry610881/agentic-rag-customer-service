from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.memory.entity import MemoryFact
from src.domain.memory.repository import MemoryFactRepository
from src.domain.memory.value_objects import MemoryFactId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.memory_fact_model import MemoryFactModel


class SQLAlchemyMemoryFactRepository(MemoryFactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: MemoryFactModel) -> MemoryFact:
        return MemoryFact(
            id=MemoryFactId(value=model.id),
            profile_id=model.profile_id,
            tenant_id=model.tenant_id,
            memory_type=model.memory_type,
            category=model.category,
            key=model.key,
            value=model.value,
            source_conversation_id=model.source_conversation_id,
            confidence=model.confidence,
            last_accessed_at=model.last_accessed_at,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, fact: MemoryFact) -> None:
        async with atomic(self._session):
            model = MemoryFactModel(
                id=fact.id.value,
                profile_id=fact.profile_id,
                tenant_id=fact.tenant_id,
                memory_type=fact.memory_type,
                category=fact.category,
                key=fact.key,
                value=fact.value,
                source_conversation_id=fact.source_conversation_id,
                confidence=fact.confidence,
                last_accessed_at=fact.last_accessed_at,
                expires_at=fact.expires_at,
                created_at=fact.created_at,
                updated_at=fact.updated_at,
            )
            await self._session.merge(model)

    async def upsert_by_key(self, fact: MemoryFact) -> None:
        async with atomic(self._session):
            stmt = select(MemoryFactModel).where(
                MemoryFactModel.profile_id == fact.profile_id,
                MemoryFactModel.key == fact.key,
            )
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.value = fact.value
                existing.category = fact.category
                existing.memory_type = fact.memory_type
                existing.confidence = fact.confidence
                existing.source_conversation_id = fact.source_conversation_id
                existing.updated_at = datetime.now(timezone.utc)
            else:
                model = MemoryFactModel(
                    id=fact.id.value,
                    profile_id=fact.profile_id,
                    tenant_id=fact.tenant_id,
                    memory_type=fact.memory_type,
                    category=fact.category,
                    key=fact.key,
                    value=fact.value,
                    source_conversation_id=fact.source_conversation_id,
                    confidence=fact.confidence,
                    last_accessed_at=fact.last_accessed_at,
                    expires_at=fact.expires_at,
                    created_at=fact.created_at,
                    updated_at=fact.updated_at,
                )
                self._session.add(model)

    async def find_by_profile(
        self,
        profile_id: str,
        *,
        memory_type: str | None = None,
        include_expired: bool = False,
    ) -> list[MemoryFact]:
        stmt = select(MemoryFactModel).where(
            MemoryFactModel.profile_id == profile_id
        )
        if memory_type is not None:
            stmt = stmt.where(MemoryFactModel.memory_type == memory_type)
        if not include_expired:
            stmt = stmt.where(
                (MemoryFactModel.expires_at.is_(None))
                | (MemoryFactModel.expires_at > datetime.now(timezone.utc))
            )
        stmt = stmt.order_by(MemoryFactModel.updated_at.desc())
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, fact_id: str) -> None:
        async with atomic(self._session):
            await self._session.execute(
                delete(MemoryFactModel).where(MemoryFactModel.id == fact_id)
            )
