"""差評根因分析用例"""

from src.domain.conversation.feedback_analysis_vo import TagCount
from src.domain.conversation.feedback_repository import FeedbackRepository


class GetTopIssuesUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self, tenant_id: str, days: int = 30, limit: int = 10
    ) -> list[TagCount]:
        return await self._feedback_repo.get_top_tags(tenant_id, days, limit)
