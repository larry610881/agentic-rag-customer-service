from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from src.domain.rag.services import VectorStore
from src.domain.rag.value_objects import SearchResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class QdrantVectorStore(VectorStore):
    def __init__(self, host: str, port: int) -> None:
        self._client = AsyncQdrantClient(host=host, port=port)

    async def ensure_collection(
        self, collection: str, vector_size: int
    ) -> None:
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if collection not in names:
            try:
                await self._client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("qdrant.collection.created", collection=collection, vector_size=vector_size)
            except Exception:
                # Another concurrent request may have created it; verify it exists
                collections = await self._client.get_collections()
                if collection not in [c.name for c in collections.collections]:
                    raise
                logger.debug("qdrant.collection.created_concurrently", collection=collection)
        else:
            logger.debug("qdrant.collection.exists", collection=collection)

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        points = [
            PointStruct(id=uid, vector=vec, payload=pay)
            for uid, vec, pay in zip(ids, vectors, payloads, strict=True)
        ]
        await self._client.upsert(
            collection_name=collection,
            points=points,
        )
        logger.info("qdrant.upsert", collection=collection, point_count=len(points))

    async def delete(
        self,
        collection: str,
        filters: dict[str, Any],
    ) -> None:
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filters.items()
        ]
        try:
            await self._client.delete(
                collection_name=collection,
                points_selector=Filter(must=conditions),
            )
            logger.info("qdrant.delete", collection=collection, filters=filters)
        except Exception:
            logger.warning("qdrant.delete.skipped", collection=collection, filters=filters)
            # Collection may not exist; safe to ignore

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        score_threshold: float = 0.3,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        query_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = Filter(must=conditions)

        response = await self._client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        points = response.points
        logger.info("qdrant.search", collection=collection, result_count=len(points))
        return [
            SearchResult(
                id=str(p.id),
                score=p.score,
                payload=p.payload or {},
            )
            for p in points
        ]
