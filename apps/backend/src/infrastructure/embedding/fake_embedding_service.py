import hashlib
import struct

from src.domain.rag.services import EmbeddingService


class FakeEmbeddingService(EmbeddingService):
    """Deterministic pseudo-random embedding for testing/development."""

    def __init__(self, vector_size: int = 1536) -> None:
        self._vector_size = vector_size

    def _hash_to_vector(self, text: str) -> list[float]:
        digest = hashlib.sha512(text.encode("utf-8")).digest()
        # Extend the hash to fill vector_size floats
        extended = digest
        while len(extended) < self._vector_size * 4:
            extended += hashlib.sha512(extended).digest()
        # Convert bytes to floats in [-1, 1]
        values = []
        for i in range(self._vector_size):
            raw = struct.unpack_from("!I", extended, i * 4)[0]
            values.append((raw / 0xFFFFFFFF) * 2 - 1)
        return values

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._hash_to_vector(text)
