"""檢索品質分析用例"""

from dataclasses import dataclass

from src.domain.conversation.feedback_analysis_vo import RetrievalQualityRecord
from src.domain.conversation.feedback_repository import FeedbackRepository


@dataclass(frozen=True)
class RetrievalQualityResult:
    records: list[RetrievalQualityRecord]
    total: int


class GetRetrievalQualityUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self, tenant_id: str, days: int = 30, limit: int = 20, offset: int = 0
    ) -> RetrievalQualityResult:
        records = await self._feedback_repo.get_negative_with_context(
            tenant_id, days, limit, offset
        )
        total = await self._feedback_repo.count_negative(tenant_id, days)
        return RetrievalQualityResult(records=records, total=total)
