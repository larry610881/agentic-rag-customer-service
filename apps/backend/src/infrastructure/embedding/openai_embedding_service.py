import asyncio
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
        batch_size: int = 50,
        max_retries: int = 5,
        timeout: float = 120.0,
        batch_delay: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._timeout = timeout
        self._batch_delay = batch_delay

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        total_batches = (len(texts) + self._batch_size - 1) // self._batch_size
        for i in range(0, len(texts), self._batch_size):
            batch_num = i // self._batch_size + 1
            if batch_num > 1:
                await asyncio.sleep(self._batch_delay)
            batch = texts[i : i + self._batch_size]
            logger.info(
                "embedding.batch",
                batch=batch_num,
                total=total_batches,
                chunk_count=len(batch),
            )
            embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def _embed_batch_with_retry(self, texts: list[str]) -> list[list[float]]:
        log = logger.bind(model=self._model, base_url=self._base_url, chunk_count=len(texts))
        for attempt in range(self._max_retries):
            try:
                return await self._call_api(texts, log)
            except httpx.HTTPStatusError as e:
                if attempt == self._max_retries - 1:
                    raise
                if e.response.status_code == 429:
                    wait = 5 * (attempt + 1)
                else:
                    wait = 2 ** attempt
                log.warning("embedding.retry", attempt=attempt + 1, wait_seconds=wait, status=e.response.status_code)
                await asyncio.sleep(wait)
            except Exception:
                if attempt == self._max_retries - 1:
                    raise
                wait = 2 ** attempt
                log.warning("embedding.retry", attempt=attempt + 1, wait_seconds=wait)
                await asyncio.sleep(wait)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def _call_api(self, texts: list[str], log):  # type: ignore[no-untyped-def]
        log.info("embedding.request", api_key_set=bool(self._api_key), api_key_prefix=self._api_key[:8] if self._api_key else "EMPTY")
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"input": texts, "model": self._model},
                    timeout=self._timeout,
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
