import hashlib
import struct

from src.domain.rag.services import EmbeddingResult, EmbeddingService


class FakeEmbeddingService(EmbeddingService):
    """Deterministic pseudo-random embedding for testing/development."""

    model = "fake-embedding"

    def __init__(self, vector_size: int = 3072) -> None:
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

    @staticmethod
    def _fake_tokens(text: str) -> int:
        """確定性的假 token 數（≈ 4 字元 1 token，至少 1）；供記帳路徑可驗證。"""
        return max(1, len(text) // 4)

    async def embed_texts_with_usage(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[self._hash_to_vector(t) for t in texts],
            model=self.model,
            total_tokens=sum(self._fake_tokens(t) for t in texts),
        )

    async def embed_query_with_usage(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[self._hash_to_vector(text)],
            model=self.model,
            total_tokens=self._fake_tokens(text),
        )
