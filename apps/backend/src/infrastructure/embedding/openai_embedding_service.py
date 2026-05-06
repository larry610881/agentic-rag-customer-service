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
        model: str = "text-embedding-3-large",
        base_url: str = "https://api.openai.com/v1",
        dimensions: int | None = None,
        batch_size: int = 50,
        max_retries: int = 5,
        timeout: float = 120.0,
        batch_delay: float = 1.0,
        retry_after_multiplier: float = 1.0,
        min_batch_size: int = 10,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._timeout = timeout
        self._batch_delay = batch_delay
        self._retry_after_multiplier = retry_after_multiplier
        self._min_batch_size = min_batch_size
        self._client = httpx.AsyncClient(timeout=self._timeout)
        self.last_total_tokens: int = 0

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.last_total_tokens = 0
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        effective_batch_size = self._batch_size
        i = 0
        batch_num = 0
        while i < len(texts):
            batch_num += 1
            if i > 0:
                await asyncio.sleep(self._batch_delay)
            batch = texts[i : i + effective_batch_size]
            logger.info(
                "embedding.batch",
                batch=batch_num,
                chunk_count=len(batch),
                batch_size=effective_batch_size,
            )
            embeddings, was_rate_limited = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)
            if was_rate_limited and effective_batch_size > self._min_batch_size:
                new_size = max(effective_batch_size // 2, self._min_batch_size)
                logger.warning(
                    "embedding.batch_size_reduced",
                    old=effective_batch_size,
                    new=new_size,
                )
                effective_batch_size = new_size
            i += len(batch)
        return all_embeddings

    async def _embed_batch_with_retry(
        self, texts: list[str]
    ) -> tuple[list[list[float]], bool]:
        log = logger.bind(
            model=self._model,
            base_url=self._base_url,
            chunk_count=len(texts),
        )
        was_rate_limited = False
        for attempt in range(self._max_retries):
            try:
                result = await self._call_api(texts, log)
                return result, was_rate_limited
            except ValueError:
                # API key 空字串等 config error → 不 retry，重試 5 次也救不回
                # 必須由人介入修 ProviderSetting 才能解
                raise
            except httpx.HTTPStatusError as e:
                if attempt == self._max_retries - 1:
                    raise
                if e.response.status_code == 429:
                    was_rate_limited = True
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        wait = float(retry_after) * self._retry_after_multiplier
                    else:
                        wait = 5 * (attempt + 1)
                # 401/403：authentication/authorization 失敗 → 不 retry
                # 通常 = key 過期 / 無權限，重試 = 浪費 quota + 拖慢 fail
                elif e.response.status_code in (401, 403):
                    log.error(
                        "embedding.auth_failed",
                        status=e.response.status_code,
                        body=e.response.text[:200],
                    )
                    raise
                else:
                    wait = 2**attempt
                log.warning(
                    "embedding.retry",
                    attempt=attempt + 1,
                    wait_seconds=wait,
                    status=e.response.status_code,
                )
                await asyncio.sleep(wait)
            except Exception:
                if attempt == self._max_retries - 1:
                    raise
                wait = 2**attempt
                log.warning("embedding.retry", attempt=attempt + 1, wait_seconds=wait)
                await asyncio.sleep(wait)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def _call_api(self, texts: list[str], log):  # type: ignore[no-untyped-def]
        # Fail-fast：API key 為空時直接 raise，避免送出 `Bearer ` 空 token
        # 觸發 httpx 的 LocalProtocolError("Illegal header value b'Bearer '")
        # 這個 error message 對 user 完全無意義且會 retry 5 次浪費時間。
        # 改 ValueError 直接讓上層 catch + retry policy 標記任務 failed，
        # error_message 帶有具體原因（API key 沒解析到）。
        # 5/6 carrefour reprocess 踩雷紀錄：worker 在 Milvus 短暫斷線後
        # 重 resolve API key 拿到空字串，原本含糊的 LocalProtocolError 讓
        # debug 浪費 30 分鐘才從 traceback 第 N 層找到 root cause。
        if not self._api_key:
            raise ValueError(
                f"Embedding API key is empty (model={self._model}, "
                f"base_url={self._base_url}). 通常表示 provider key resolver "
                "拿不到值（DB session 失效 / ProviderSetting 缺 / env 沒設）。"
                "請檢查 tenant 的 ProviderSetting 是否完整。"
            )
        key_prefix = self._api_key[:8] if self._api_key else "EMPTY"
        log.info(
            "embedding.request",
            api_key_set=bool(self._api_key),
            api_key_prefix=key_prefix,
        )
        start = time.perf_counter()
        try:
            resp = await self._client.post(
                f"{self._base_url}/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "input": texts,
                    "model": self._model,
                    **({"dimensions": self._dimensions} if self._dimensions else {}),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            usage = data.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            self.last_total_tokens += total_tokens
            log.info(
                "embedding.done",
                latency_ms=elapsed_ms,
                total_tokens=total_tokens,
            )
            return [item["embedding"] for item in data["data"]]
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.exception("embedding.failed", latency_ms=elapsed_ms)
            raise

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_texts([text])
        return results[0]
