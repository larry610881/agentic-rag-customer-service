"""記憶體版異常分數儲存（測試 / 單機；Issue #68 P7a）。時鐘可注入以測衰減與 TTL。"""

import time
from collections.abc import Callable

from src.domain.abuse.store import AbuseScoreStore


class InMemoryAbuseScoreStore(AbuseScoreStore):
    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._scores: dict[str, tuple[float, float, float]] = {}  # score, ts, expires
        self._levels: dict[str, tuple[int, float]] = {}            # level, until
        self._counters: dict[str, tuple[int, float]] = {}          # count, expires
        self.fail = False  # 測試用：模擬儲存失效

    def _check(self) -> None:
        if self.fail:
            raise ConnectionError("abuse store unavailable")

    def _decayed(self, key: str, decay: float) -> float:
        entry = self._scores.get(key)
        if entry is None:
            return 0.0
        score, ts, expires = entry
        now = self._clock()
        if expires <= now:
            self._scores.pop(key, None)
            return 0.0
        return max(0.0, score - decay * (now - ts) / 60.0)

    async def add_score(
        self, key: str, delta: float, decay_per_minute: float, ttl_seconds: int
    ) -> float:
        self._check()
        now = self._clock()
        score = self._decayed(key, decay_per_minute) + delta
        self._scores[key] = (score, now, now + ttl_seconds)
        return score

    async def get_score(self, key: str, decay_per_minute: float) -> float:
        self._check()
        return self._decayed(key, decay_per_minute)

    async def set_level(self, key: str, level: int, ttl_seconds: int) -> None:
        self._check()
        self._levels[f"{key}:lvl"] = (level, self._clock() + ttl_seconds)

    async def get_level(self, key: str) -> tuple[int, int] | None:
        self._check()
        entry = self._levels.get(f"{key}:lvl")
        if entry is None:
            return None
        level, until = entry
        remaining = until - self._clock()
        if remaining <= 0:
            self._levels.pop(f"{key}:lvl", None)
            return None
        return level, int(remaining) or 1

    async def clear(self, key: str) -> None:
        self._check()
        self._scores.pop(key, None)
        self._levels.pop(f"{key}:lvl", None)

    async def incr_counter(self, key: str, ttl_seconds: int) -> int:
        self._check()
        now = self._clock()
        count, expires = self._counters.get(key, (0, 0.0))
        if expires <= now:
            count, expires = 0, now + ttl_seconds
        count += 1
        self._counters[key] = (count, expires)
        return count

    async def reset_counter(self, key: str) -> None:
        self._check()
        self._counters.pop(key, None)

    async def list_locked(self, prefix: str) -> list[tuple[str, int, int]]:
        self._check()
        now = self._clock()
        out: list[tuple[str, int, int]] = []
        for lvl_key, (level, until) in list(self._levels.items()):
            if not lvl_key.startswith(prefix):
                continue
            remaining = until - now
            if remaining <= 0:
                self._levels.pop(lvl_key, None)
                continue
            out.append((lvl_key[: -len(":lvl")], level, int(remaining) or 1))
        return out
