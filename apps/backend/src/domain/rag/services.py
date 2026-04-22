from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from src.domain.rag.value_objects import LLMResult, SearchResult


class EmbeddingService(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...


class VectorStore(ABC):
    @abstractmethod
    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None: ...

    @abstractmethod
    async def ensure_collection(
        self, collection: str, vector_size: int
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        score_threshold: float = 0.3,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    async def delete(
        self,
        collection: str,
        filters: dict[str, Any],
    ) -> None: ...

    async def fetch_vectors(
        self,
        collection: str,
        ids: list[str],
    ) -> list[tuple[str, list[float], dict[str, Any]]]:
        """Fetch vectors + payloads by IDs. Returns list of (id, vector, payload)."""
        return []

    # --- S-KB-Studio.1 新增：Admin Dashboard / 單 chunk re-embed 用 ---

    async def list_collections(self) -> list[dict[str, Any]]:
        """列出所有 collection。每筆含 {name, row_count}。
        預設空實作；Milvus 實作覆寫。
        """
        return []

    async def get_collection_stats(
        self, collection: str
    ) -> dict[str, Any]:
        """回傳 collection 詳細：
        {row_count, loaded, indexes: [{field, index_type}], vector_dim}。"""
        return {}

    async def upsert_single(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """單 chunk upsert（for re-embed）。payload 必含 tenant_id（caller 驗證）。
        預設 fallback：呼叫批次 upsert。Milvus 實作可優化。"""
        await self.upsert(
            collection=collection,
            ids=[id],
            vectors=[vector],
            payloads=[payload],
        )

    async def update_payload(
        self,
        collection: str,
        id: str,
        payload_diff: dict[str, Any],
    ) -> None:
        """只改 payload 不改向量（metadata-only 操作）。
        Milvus 實作覆寫，預設 no-op。"""
        return None

    async def count_by_filter(
        self,
        collection: str,
        filters: dict[str, Any],
    ) -> int:
        """回傳符合 filter 的 row 數。Milvus 實作覆寫，預設 0。"""
        return 0


class LLMService(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
    ) -> LLMResult: ...

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        usage_collector: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]: ...  # pragma: no cover
