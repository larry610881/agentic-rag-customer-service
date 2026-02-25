"""滿意度趨勢查詢用例"""

from src.domain.conversation.feedback_analysis_vo import DailyFeedbackStat
from src.domain.conversation.feedback_repository import FeedbackRepository


class GetSatisfactionTrendUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self, tenant_id: str, days: int = 30
    ) -> list[DailyFeedbackStat]:
        return await self._feedback_repo.get_daily_trend(tenant_id, days)
