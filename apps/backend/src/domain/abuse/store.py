"""異常分數儲存 port（Issue #68 P7a）

- 分數：線性衰減（每分鐘 -decay）+ TTL；add_score 回衰減後再加分的新值。
- 等級鎖：升級時設 (level, until)；到期自然回復。
- 計數器：節奏（每分鐘訊息數）與連續 unrouted 用。

實作必須 fail-open：儲存失效時丟例外，由 service 接住並放行。
"""

from abc import ABC, abstractmethod


class AbuseScoreStore(ABC):
    @abstractmethod
    async def add_score(
        self, key: str, delta: float, decay_per_minute: float, ttl_seconds: int
    ) -> float: ...

    @abstractmethod
    async def get_score(self, key: str, decay_per_minute: float) -> float: ...

    @abstractmethod
    async def set_level(self, key: str, level: int, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def get_level(self, key: str) -> tuple[int, int] | None:
        """回 (level, 剩餘秒數)；無鎖回 None。"""
        ...

    @abstractmethod
    async def clear(self, key: str) -> None: ...

    @abstractmethod
    async def incr_counter(self, key: str, ttl_seconds: int) -> int: ...

    @abstractmethod
    async def list_locked(self, prefix: str) -> list[tuple[str, int, int]]:
        """列出 prefix 底下所有等級鎖：(主體 key, level, 剩餘秒)。"""
        ...

    @abstractmethod
    async def reset_counter(self, key: str) -> None: ...
