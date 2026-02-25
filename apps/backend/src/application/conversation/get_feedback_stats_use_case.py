"""回饋統計 Use Case"""

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
    def __init__(self, feedback_repository: FeedbackRepository):
        self._feedback_repo = feedback_repository

    async def execute(self, tenant_id: str) -> FeedbackStats:
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

        return FeedbackStats(
            total=total,
            thumbs_up=thumbs_up,
            thumbs_down=thumbs_down,
            satisfaction_rate=satisfaction_rate,
        )
