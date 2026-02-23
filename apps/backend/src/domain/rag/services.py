from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from src.domain.rag.value_objects import SearchResult


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


class LLMService(ABC):
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> str: ...

    @abstractmethod
    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> AsyncIterator[str]: ...  # pragma: no cover
