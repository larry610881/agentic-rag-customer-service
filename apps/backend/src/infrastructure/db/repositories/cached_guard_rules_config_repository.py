"""Guard 設定 in-process TTL 快取 — Issue #52 E2

現況每則 LINE 訊息 check_input + check_output 各查一次 guard_rules_config
（singleton row），一天下來全是重複讀。Guard 設定變更頻率極低（admin 手動），
60 秒 staleness 完全可接受。

比照 dynamic_llm_factory 的 module-level TTLCache 前例：cache 放 module
層級讓 per-request Factory 建的 repo 實例共享；寫入時全清。
"""

from threading import Lock

from cachetools import TTLCache

from src.domain.security.guard_config import (
    GuardRulesConfig,
    GuardRulesConfigRepository,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 60
_CACHE_KEY = "default"
# None（設定不存在）也要快取，否則 POC 未建設定時每則訊息照樣打 DB
_SENTINEL_NONE = object()
_CACHE: TTLCache = TTLCache(maxsize=4, ttl=_CACHE_TTL_SECONDS)
_LOCK = Lock()


def invalidate_guard_rules_cache() -> None:
    with _LOCK:
        _CACHE.clear()


class CachedGuardRulesConfigRepository(GuardRulesConfigRepository):
    def __init__(self, inner: GuardRulesConfigRepository) -> None:
        self._inner = inner

    async def get(self) -> GuardRulesConfig | None:
        with _LOCK:
            cached = _CACHE.get(_CACHE_KEY)
        if cached is not None:
            return None if cached is _SENTINEL_NONE else cached

        config = await self._inner.get()
        with _LOCK:
            _CACHE[_CACHE_KEY] = config if config is not None else _SENTINEL_NONE
        return config

    async def save(self, config: GuardRulesConfig) -> None:
        await self._inner.save(config)
        invalidate_guard_rules_cache()
        logger.info("guard_rules_cache.invalidated_by_save")
