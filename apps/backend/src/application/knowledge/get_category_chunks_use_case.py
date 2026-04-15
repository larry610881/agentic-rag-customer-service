"""取得分類下的 chunks + 向量聚合度（cosine similarity to centroid）"""

from dataclasses import dataclass

import numpy as np

from src.domain.knowledge.repository import ChunkCategoryRepository, DocumentRepository
from src.domain.rag.services import VectorStore
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CategoryChunkItem:
    id: str
    content: str
    context_text: str
    chunk_index: int
    cohesion_score: float  # 1 - cosine_distance to centroid


@dataclass
class CategoryChunksResult:
    category_id: str
    category_name: str
    chunk_count: int
    chunks: list[CategoryChunkItem]


class GetCategoryChunksUseCase:
    def __init__(
        self,
        category_repository: ChunkCategoryRepository,
        document_repository: DocumentRepository,
        vector_store: VectorStore,
    ) -> None:
        self._cat_repo = category_repository
        self._doc_repo = document_repository
        self._vector_store = vector_store

    async def execute(self, kb_id: str, category_id: str) -> CategoryChunksResult | None:
        cat = await self._cat_repo.find_by_id(category_id)
        if cat is None:
            return None

        # Fetch chunks from DB
        chunks = await self._doc_repo.find_chunks_by_category(category_id)
        if not chunks:
            return CategoryChunksResult(
                category_id=cat.id,
                category_name=cat.name,
                chunk_count=0,
                chunks=[],
            )

        # Fetch vectors from Milvus
        chunk_ids = [c.id.value for c in chunks]
        collection = f"kb_{kb_id}"
        try:
            vector_results = await self._vector_store.fetch_vectors(
                collection, chunk_ids
            )
        except Exception:
            logger.warning("category_chunks.fetch_vectors_failed", exc_info=True)
            vector_results = []

        # Build id → vector map
        vector_map: dict[str, list[float]] = {}
        for vid, vec, _ in vector_results:
            if vec:
                vector_map[vid] = vec

        # Calculate centroid + cohesion scores
        cohesion_map: dict[str, float] = {}
        if vector_map:
            vectors = list(vector_map.values())
            ids_with_vec = list(vector_map.keys())
            arr = np.array(vectors)
            centroid = arr.mean(axis=0)

            # Cosine similarity: dot(a, b) / (norm(a) * norm(b))
            centroid_norm = np.linalg.norm(centroid)
            if centroid_norm > 0:
                for i, vid in enumerate(ids_with_vec):
                    vec_norm = np.linalg.norm(arr[i])
                    if vec_norm > 0:
                        sim = float(np.dot(arr[i], centroid) / (vec_norm * centroid_norm))
                        cohesion_map[vid] = round(max(0.0, min(1.0, sim)), 3)

        # Build result, sorted by cohesion (lowest last for PM to spot outliers)
        items = [
            CategoryChunkItem(
                id=c.id.value,
                content=c.content,
                context_text=c.context_text,
                chunk_index=c.chunk_index,
                cohesion_score=cohesion_map.get(c.id.value, 0.0),
            )
            for c in chunks
        ]
        items.sort(key=lambda x: x.cohesion_score, reverse=True)

        return CategoryChunksResult(
            category_id=cat.id,
            category_name=cat.name,
            chunk_count=len(items),
            chunks=items,
        )
