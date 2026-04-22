from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.knowledge.entity import ChunkCategory
from src.domain.knowledge.repository import ChunkCategoryRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.chunk_category_model import ChunkCategoryModel
from src.infrastructure.db.models.chunk_model import ChunkModel


class SQLAlchemyChunkCategoryRepository(ChunkCategoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: ChunkCategoryModel) -> ChunkCategory:
        return ChunkCategory(
            id=model.id,
            kb_id=model.kb_id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            chunk_count=model.chunk_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, category: ChunkCategory) -> None:
        async with atomic(self._session):
            model = ChunkCategoryModel(
                id=category.id,
                kb_id=category.kb_id,
                tenant_id=category.tenant_id,
                name=category.name,
                description=category.description,
                chunk_count=category.chunk_count,
            )
            self._session.add(model)

    async def save_batch(self, categories: list[ChunkCategory]) -> None:
        async with atomic(self._session):
            models = [
                ChunkCategoryModel(
                    id=c.id,
                    kb_id=c.kb_id,
                    tenant_id=c.tenant_id,
                    name=c.name,
                    description=c.description,
                    chunk_count=c.chunk_count,
                )
                for c in categories
            ]
            self._session.add_all(models)

    async def find_by_kb(self, kb_id: str) -> list[ChunkCategory]:
        stmt = (
            select(ChunkCategoryModel)
            .where(ChunkCategoryModel.kb_id == kb_id)
            .order_by(ChunkCategoryModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_id(self, category_id: str) -> ChunkCategory | None:
        stmt = select(ChunkCategoryModel).where(
            ChunkCategoryModel.id == category_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update_name(self, category_id: str, name: str) -> None:
        async with atomic(self._session):
            await self._session.execute(
                update(ChunkCategoryModel)
                .where(ChunkCategoryModel.id == category_id)
                .values(name=name)
            )

    async def delete_by_kb(self, kb_id: str) -> None:
        async with atomic(self._session):
            await self._session.execute(
                delete(ChunkCategoryModel).where(
                    ChunkCategoryModel.kb_id == kb_id
                )
            )

    async def update_chunk_counts(self, kb_id: str) -> None:
        """Recalculate chunk_count for all categories in a KB."""
        async with atomic(self._session):
            sub = (
                select(
                    ChunkModel.category_id,
                    func.count().label("cnt"),
                )
                .where(ChunkModel.category_id.isnot(None))
                .group_by(ChunkModel.category_id)
                .subquery()
            )
            # Reset all to 0 first
            await self._session.execute(
                update(ChunkCategoryModel)
                .where(ChunkCategoryModel.kb_id == kb_id)
                .values(chunk_count=0)
            )
            # Update with actual counts
            rows = await self._session.execute(
                select(sub.c.category_id, sub.c.cnt)
            )
            for cat_id, cnt in rows.all():
                await self._session.execute(
                    update(ChunkCategoryModel)
                    .where(ChunkCategoryModel.id == cat_id)
                    .values(chunk_count=cnt)
                )

    # --- S-KB-Studio.1 新增實作 ---

    async def delete_by_id(self, category_id: str) -> None:
        """刪除單一 category；chunks.category_id 會 SET NULL by FK constraint
        (chunks.category_id ON DELETE SET NULL 若沒設則需 migration 補)。"""
        async with atomic(self._session):
            # 手動把 chunks.category_id 設 NULL（保險；不靠 FK cascade）
            await self._session.execute(
                update(ChunkModel)
                .where(ChunkModel.category_id == category_id)
                .values(category_id=None)
            )
            await self._session.execute(
                delete(ChunkCategoryModel).where(
                    ChunkCategoryModel.id == category_id
                )
            )

    async def assign_chunks(
        self, category_id: str, chunk_ids: list[str]
    ) -> None:
        """批次指派：實作等同 DocumentRepository.update_chunks_category()
        但從 category-centric 視角入口。"""
        if not chunk_ids:
            return
        async with atomic(self._session):
            await self._session.execute(
                update(ChunkModel)
                .where(ChunkModel.id.in_(chunk_ids))
                .values(category_id=category_id)
            )
