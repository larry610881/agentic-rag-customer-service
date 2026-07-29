"""Embedding 查詢快取 Decorator — Issue #52 E1

embedding 是 (model, text) 的純函數：同模型 + 同文字永遠得到同一向量，
所以查詢向量可以長 TTL 快取。客服場景問句重複度高，命中時省下整段
Embedding API 呼叫（實測 ~300-500ms）。

租戶隔離說明（對照 .claude/rules/security.md「快取 embedding 結果時需
考慮租戶隔離」）：查詢向量僅由「查詢文字本身 + 模型」決定，不含任何
租戶知識庫資料；要讀到某筆快取必須先持有一模一樣的查詢文字，而該文字
算出的向量對任何人都相同 —— 共用快取不構成跨租戶洩漏，反而提升命中率。
文件 ingestion 的 embed_texts 不快取（批次幾乎不重複，只會塞爆 Redis）。
"""

import base64
import binascii
import hashlib
import struct
import time

from src.domain.rag.services import EmbeddingService
from src.domain.shared.cache_service import CacheService
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "emb:q"
_DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 天；key 含模型名，換模型自動失效


def encode_vector(vector: list[float]) -> str:
    """float32 raw bytes → base64 str（3072 維 ≈ 16KB，JSON 會膨脹到 60KB+）"""
    raw = struct.pack(f"{len(vector)}f", *vector)
    return base64.b64encode(raw).decode("ascii")


def decode_vector(value: str) -> list[float]:
    raw = base64.b64decode(value.encode("ascii"), validate=True)
    if len(raw) % 4 != 0:
        raise ValueError("corrupted embedding cache value")
    return list(struct.unpack(f"{len(raw) // 4}f", raw))


class CachedEmbeddingService(EmbeddingService):
    """包在任意 EmbeddingService 外的 Redis 查詢快取層。

    fail-open：快取讀寫失敗（RedisCacheService 已對 RedisError 吞錯）或
    內容毀損時，一律視為未命中直接呼叫內層服務，不影響檢索可用性。
    """

    def __init__(
        self,
        inner: EmbeddingService,
        cache: CacheService,
        model: str,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._model = model
        self._ttl_seconds = ttl_seconds

    def _key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self._model}\x00{text}".encode()).hexdigest()
        return f"{_KEY_PREFIX}:{digest}"

    async def embed_query(self, text: str) -> list[float]:
        normalized = text.strip()
        key = self._key(normalized)
        start = time.perf_counter()

        cached = await self._cache.get(key)
        if cached is not None:
            try:
                vector = decode_vector(cached)
            except (ValueError, binascii.Error):
                logger.warning("embedding_cache.corrupted", key=key)
            else:
                logger.info(
                    "embedding_cache.hit",
                    key=key,
                    latency_ms=round((time.perf_counter() - start) * 1000, 1),
                )
                return vector

        vector = await self._inner.embed_query(normalized)
        try:
            await self._cache.set(
                key, encode_vector(vector), ttl_seconds=self._ttl_seconds
            )
        except Exception:  # 寫入失敗不影響回傳
            logger.warning("embedding_cache.set_failed", key=key)
        logger.info(
            "embedding_cache.miss",
            key=key,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return vector

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self._inner.embed_texts(texts)
