"""檢索品質分析用例"""

from dataclasses import dataclass

from src.domain.conversation.feedback_analysis_vo import RetrievalQualityRecord
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import Rating


@dataclass(frozen=True)
class RetrievalQualityResult:
    records: list[RetrievalQualityRecord]
    total: int


@dataclass(frozen=True)
class ChunkQualityInfo:
    feedback_id: str
    message_id: str
    conversation_id: str
    quality: str


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

    def analyze_chunk_quality(
        self, feedback_items: list[Feedback]
    ) -> list[ChunkQualityInfo]:
        """Analyze chunk quality from negative feedback."""
        low_quality_chunks: list[ChunkQualityInfo] = []
        for fb in feedback_items:
            if fb.rating == Rating.THUMBS_DOWN:
                low_quality_chunks.append(
                    ChunkQualityInfo(
                        feedback_id=fb.id.value,
                        message_id=fb.message_id,
                        conversation_id=fb.conversation_id,
                        quality="low",
                    )
                )
        return low_quality_chunks
