import time

import httpx

from src.domain.rag.services import EmbeddingService
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        log = logger.bind(model=self._model, base_url=self._base_url, chunk_count=len(texts))
        log.info("embedding.request", api_key_set=bool(self._api_key), api_key_prefix=self._api_key[:8] if self._api_key else "EMPTY")
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"input": texts, "model": self._model},
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                log.info("embedding.done", latency_ms=elapsed_ms)
                return [item["embedding"] for item in data["data"]]
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.exception("embedding.failed", latency_ms=elapsed_ms)
            raise

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_texts([text])
        return results[0]
