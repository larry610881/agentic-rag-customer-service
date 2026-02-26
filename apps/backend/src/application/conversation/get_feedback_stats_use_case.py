"""回饋統計 Use Case"""

import json
from dataclasses import asdict, dataclass

from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import Rating
from src.domain.shared.cache_service import CacheService


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
        cache_service: CacheService | None = None,
        cache_ttl: int = 60,
    ):
        self._feedback_repo = feedback_repository
        self._cache_service = cache_service
        self._cache_ttl = cache_ttl

    async def execute(self, tenant_id: str) -> FeedbackStats:
        cache_key = f"feedback_stats:{tenant_id}"
        if self._cache_service is not None:
            cached = await self._cache_service.get(cache_key)
            if cached is not None:
                d = json.loads(cached)
                return FeedbackStats(**d)

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
        if self._cache_service is not None:
            await self._cache_service.set(
                cache_key,
                json.dumps(asdict(stats)),
                ttl_seconds=self._cache_ttl,
            )
        return stats
