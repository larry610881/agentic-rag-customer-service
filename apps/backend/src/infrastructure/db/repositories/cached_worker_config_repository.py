"""Worker 設定 in-process TTL 快取 — Issue #52 E2

每則 LINE 訊息 routing 前都 find_by_bot_id 查一次 bot_workers（uncached）。
Worker 設定只在 admin 後台變更，60 秒 staleness 可接受。

失效策略：save/delete 一律全清 —— delete 只拿得到 worker_id 反推不了
bot_id，而 admin 寫入頻率極低，全清最簡單且不會有漏失效的死角。
"""

from threading import Lock

from cachetools import TTLCache

from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 60
_CACHE: TTLCache = TTLCache(maxsize=256, ttl=_CACHE_TTL_SECONDS)
_LOCK = Lock()


def invalidate_worker_config_cache() -> None:
    with _LOCK:
        _CACHE.clear()


class CachedWorkerConfigRepository(WorkerConfigRepository):
    def __init__(self, inner: WorkerConfigRepository) -> None:
        self._inner = inner

    async def find_by_bot_id(self, bot_id: str) -> list[WorkerConfig]:
        with _LOCK:
            cached = _CACHE.get(bot_id)
        if cached is not None:
            return list(cached)

        workers = await self._inner.find_by_bot_id(bot_id)
        with _LOCK:
            _CACHE[bot_id] = list(workers)
        return workers

    async def find_by_id(self, worker_id: str) -> WorkerConfig | None:
        return await self._inner.find_by_id(worker_id)

    async def save(self, worker: WorkerConfig) -> None:
        await self._inner.save(worker)
        invalidate_worker_config_cache()
        logger.info("worker_config_cache.invalidated_by_save", bot_id=worker.bot_id)

    async def delete(self, worker_id: str) -> None:
        await self._inner.delete(worker_id)
        invalidate_worker_config_cache()
        logger.info("worker_config_cache.invalidated_by_delete", worker_id=worker_id)
