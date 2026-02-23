"""記錄 Token 使用量用例"""

from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.entity import UsageRecord
from src.domain.usage.repository import UsageRepository


class RecordUsageUseCase:
    def __init__(self, usage_repository: UsageRepository) -> None:
        self._repo = usage_repository

    async def execute(
        self,
        tenant_id: str,
        request_type: str,
        usage: TokenUsage | None,
    ) -> None:
        if usage is None or usage.total_tokens == 0:
            return

        record = UsageRecord(
            tenant_id=tenant_id,
            request_type=request_type,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost=usage.estimated_cost,
        )
        await self._repo.save(record)
