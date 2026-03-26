"""滿意度趨勢查詢用例"""

from datetime import datetime

from src.domain.conversation.feedback_analysis_vo import DailyFeedbackStat
from src.domain.conversation.feedback_repository import FeedbackRepository


class GetSatisfactionTrendUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DailyFeedbackStat]:
        return await self._feedback_repo.get_daily_trend(
            tenant_id, start_date, end_date
        )
