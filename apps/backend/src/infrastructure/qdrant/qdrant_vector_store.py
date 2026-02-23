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


class QdrantVectorStore(VectorStore):
    def __init__(self, host: str, port: int) -> None:
        self._client = AsyncQdrantClient(host=host, port=port)

    async def ensure_collection(
        self, collection: str, vector_size: int
    ) -> None:
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if collection not in names:
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )

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

        points = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )
        return [
            SearchResult(
                id=str(p.id),
                score=p.score,
                payload=p.payload or {},
            )
            for p in points
        ]
