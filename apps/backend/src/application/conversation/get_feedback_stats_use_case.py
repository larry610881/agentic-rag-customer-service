"""回饋統計 Use Case"""

import time
from dataclasses import dataclass

from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import Rating


@dataclass(frozen=True)
class FeedbackStats:
    total: int
    thumbs_up: int
    thumbs_down: int
    satisfaction_rate: float


class GetFeedbackStatsUseCase:
    def __init__(
        self,
        feedback_repository: FeedbackRepository,
        cache_ttl: float = 60.0,
    ):
        self._feedback_repo = feedback_repository
        self._cache: dict[str, tuple[FeedbackStats, float]] = {}
        self._cache_ttl = cache_ttl

    async def execute(self, tenant_id: str) -> FeedbackStats:
        now = time.monotonic()
        cached = self._cache.get(tenant_id)
        if cached is not None:
            stats, ts = cached
            if now - ts < self._cache_ttl:
                return stats

        total = await self._feedback_repo.count_by_tenant_and_rating(
            tenant_id
        )
        thumbs_up = await self._feedback_repo.count_by_tenant_and_rating(
            tenant_id, Rating.THUMBS_UP
        )
        thumbs_down = total - thumbs_up

        satisfaction_rate = (
            round(thumbs_up / total * 100, 1) if total > 0 else 0.0
        )

        stats = FeedbackStats(
            total=total,
            thumbs_up=thumbs_up,
            thumbs_down=thumbs_down,
            satisfaction_rate=satisfaction_rate,
        )
        self._cache[tenant_id] = (stats, now)
        return stats
