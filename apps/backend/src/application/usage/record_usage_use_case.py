"""記錄 Token 使用量用例"""

from src.domain.platform.model_registry import DEFAULT_MODELS
from src.domain.rag.pricing import calculate_usage
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
        bot_id: str | None = None,
    ) -> None:
        if usage is None or usage.total_tokens == 0:
            return

        # Fallback: ReAct 路徑的 TokenUsage 可能缺少 cost，從 registry 重算
        cost = usage.estimated_cost
        if cost == 0.0 and usage.total_tokens > 0:
            cost = self._estimate_cost_from_registry(
                usage.model, usage.input_tokens, usage.output_tokens,
            )

        record = UsageRecord(
            tenant_id=tenant_id,
            request_type=request_type,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost=cost,
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            bot_id=bot_id,
        )
        await self._repo.save(record)

    @staticmethod
    def _estimate_cost_from_registry(
        model: str, input_tokens: int, output_tokens: int,
    ) -> float:
        """從 DEFAULT_MODELS registry 查定價，計算成本。"""
        pricing: dict[str, dict[str, float]] = {}
        for provider_models in DEFAULT_MODELS.values():
            for m in provider_models.get("llm", []):
                if m.get("input_price", 0) > 0 or m.get("output_price", 0) > 0:
                    entry: dict[str, float] = {
                        "input": m["input_price"],
                        "output": m["output_price"],
                    }
                    if m.get("cache_read_price", 0) > 0:
                        entry["cache_read"] = m["cache_read_price"]
                    if m.get("cache_creation_price", 0) > 0:
                        entry["cache_creation"] = m["cache_creation_price"]
                    pricing[m["model_id"]] = entry
        return calculate_usage(model, input_tokens, output_tokens, pricing).estimated_cost
