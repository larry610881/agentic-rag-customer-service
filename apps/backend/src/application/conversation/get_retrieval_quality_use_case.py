"""檢索品質分析用例"""

from src.domain.conversation.feedback_analysis_vo import RetrievalQualityRecord
from src.domain.conversation.feedback_repository import FeedbackRepository


class GetRetrievalQualityUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self, tenant_id: str, days: int = 30, limit: int = 20
    ) -> list[RetrievalQualityRecord]:
        return await self._feedback_repo.get_negative_with_context(
            tenant_id, days, limit
        )
