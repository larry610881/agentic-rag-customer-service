"""SQLAlchemy implementation of WikiGraphRepository."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.repository import WikiGraphRepository
from src.domain.wiki.value_objects import WikiGraphId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.wiki_graph_model import WikiGraphModel


class SQLAlchemyWikiGraphRepository(WikiGraphRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: WikiGraphModel) -> WikiGraph:
        return WikiGraph(
            id=WikiGraphId(value=model.id),
            tenant_id=model.tenant_id,
            bot_id=model.bot_id,
            kb_id=model.kb_id,
            status=model.status,
            nodes=dict(model.nodes or {}),
            edges=dict(model.edges or {}),
            backlinks={
                k: list(v) for k, v in (model.backlinks or {}).items()
            },
            clusters=list(model.clusters or []),
            metadata=dict(model.wiki_metadata or {}),
            compiled_at=model.compiled_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, wiki_graph: WikiGraph) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                WikiGraphModel, wiki_graph.id.value
            )
            if existing:
                existing.tenant_id = wiki_graph.tenant_id
                existing.bot_id = wiki_graph.bot_id
                existing.kb_id = wiki_graph.kb_id
                existing.status = wiki_graph.status
                existing.nodes = wiki_graph.nodes
                existing.edges = wiki_graph.edges
                existing.backlinks = wiki_graph.backlinks
                existing.clusters = wiki_graph.clusters
                existing.wiki_metadata = wiki_graph.metadata
                existing.compiled_at = wiki_graph.compiled_at
                existing.updated_at = wiki_graph.updated_at
            else:
                model = WikiGraphModel(
                    id=wiki_graph.id.value,
                    tenant_id=wiki_graph.tenant_id,
                    bot_id=wiki_graph.bot_id,
                    kb_id=wiki_graph.kb_id,
                    status=wiki_graph.status,
                    nodes=wiki_graph.nodes,
                    edges=wiki_graph.edges,
                    backlinks=wiki_graph.backlinks,
                    clusters=wiki_graph.clusters,
                    wiki_metadata=wiki_graph.metadata,
                    compiled_at=wiki_graph.compiled_at,
                    created_at=wiki_graph.created_at,
                    updated_at=wiki_graph.updated_at,
                )
                self._session.add(model)

    async def find_by_id(
        self, wiki_graph_id: str
    ) -> WikiGraph | None:
        stmt = select(WikiGraphModel).where(
            WikiGraphModel.id == wiki_graph_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def find_by_bot_id(
        self, tenant_id: str, bot_id: str
    ) -> WikiGraph | None:
        stmt = select(WikiGraphModel).where(
            WikiGraphModel.tenant_id == tenant_id,
            WikiGraphModel.bot_id == bot_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[WikiGraph]:
        stmt = (
            select(WikiGraphModel)
            .where(WikiGraphModel.tenant_id == tenant_id)
            .order_by(WikiGraphModel.created_at)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_tenant(self, tenant_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(WikiGraphModel)
            .where(WikiGraphModel.tenant_id == tenant_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete(self, wiki_graph_id: str) -> None:
        async with atomic(self._session):
            await self._session.execute(
                delete(WikiGraphModel).where(
                    WikiGraphModel.id == wiki_graph_id
                )
            )

    async def delete_by_bot_id(
        self, tenant_id: str, bot_id: str
    ) -> None:
        async with atomic(self._session):
            await self._session.execute(
                delete(WikiGraphModel).where(
                    WikiGraphModel.tenant_id == tenant_id,
                    WikiGraphModel.bot_id == bot_id,
                )
            )
