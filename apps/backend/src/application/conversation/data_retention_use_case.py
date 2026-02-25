"""資料保留策略用例"""

from datetime import datetime, timedelta, timezone

from src.domain.conversation.feedback_repository import FeedbackRepository


class DataRetentionUseCase:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repo = feedback_repository

    async def execute(
        self, tenant_id: str, *, months: int = 6
    ) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
        return await self._feedback_repo.delete_before_date(tenant_id, cutoff)
