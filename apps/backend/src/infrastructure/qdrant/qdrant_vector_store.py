from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.domain.rag.services import VectorStore


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
