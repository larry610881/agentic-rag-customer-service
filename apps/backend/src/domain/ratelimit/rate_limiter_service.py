from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int | None = None  # seconds


class RateLimiterService(ABC):
    @abstractmethod
    async def check_rate_limit(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitResult: ...
