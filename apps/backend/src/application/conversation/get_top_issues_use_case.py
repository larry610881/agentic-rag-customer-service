"""差評根因分析用例"""

from datetime import datetime

from src.domain.conversation.feedback_analysis_vo import TagCount
from src.domain.conversation.feedback_repository import FeedbackRepository


class GetTopIssuesUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[TagCount]:
        return await self._feedback_repo.get_top_tags(
            tenant_id, start_date, end_date, limit
        )
