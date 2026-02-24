from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.repository import ChunkRepository
from src.domain.knowledge.value_objects import ChunkId
from src.infrastructure.db.models.chunk_model import ChunkModel


class SQLAlchemyChunkRepository(ChunkRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: ChunkModel) -> Chunk:
        return Chunk(
            id=ChunkId(value=model.id),
            document_id=model.document_id,
            tenant_id=model.tenant_id,
            content=model.content,
            chunk_index=model.chunk_index,
            metadata=model.metadata_ or {},
        )

    async def save_batch(self, chunks: list[Chunk]) -> None:
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
        await self._session.commit()

    async def delete_by_document(self, document_id: str) -> None:
        stmt = delete(ChunkModel).where(ChunkModel.document_id == document_id)
        await self._session.execute(stmt)
        await self._session.commit()

    async def find_by_document(
        self, document_id: str
    ) -> list[Chunk]:
        stmt = (
            select(ChunkModel)
            .where(ChunkModel.document_id == document_id)
            .order_by(ChunkModel.chunk_index)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]
