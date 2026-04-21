"""記錄 Token 使用量用例"""

from typing import TYPE_CHECKING

import structlog

from src.domain.platform.model_registry import DEFAULT_MODELS
from src.domain.rag.pricing import calculate_usage
from src.domain.rag.value_objects import TokenUsage
from src.domain.tenant.entity import Tenant
from src.domain.usage.category import UsageCategory
from src.domain.usage.entity import UsageRecord
from src.domain.usage.repository import UsageRepository

if TYPE_CHECKING:
    from src.application.ledger.deduct_tokens_use_case import (
        DeductTokensUseCase,
    )
    from src.domain.tenant.repository import TenantRepository

logger = structlog.get_logger(__name__)

# Token-Gov: request_type 白名單 — 只接受 UsageCategory enum 值，擋掉 legacy 字串與 typo
_VALID_CATEGORIES: frozenset[str] = frozenset(c.value for c in UsageCategory)


class RecordUsageUseCase:
    def __init__(
        self,
        usage_repository: UsageRepository,
        deduct_tokens: "DeductTokensUseCase | None" = None,
        tenant_repository: "TenantRepository | None" = None,
    ) -> None:
        self._repo = usage_repository
        # S-Token-Gov.2: 注入後會在每筆 usage 寫入後扣 ledger
        self._deduct = deduct_tokens
        self._tenant_repo = tenant_repository

    @staticmethod
    def _should_count_for_quota(tenant: Tenant, category: str) -> bool:
        """判斷該租戶 + 該 category 是否計入額度。

        - included_categories is None → 全部計入（safe default）
        - included_categories == [] → 全部不計入（POC 免計費）
        - 否則 → 只計入列表內的
        """
        if tenant.included_categories is None:
            return True
        return category in tenant.included_categories

    async def execute(
        self,
        tenant_id: str,
        request_type: str,
        usage: TokenUsage | None,
        bot_id: str | None = None,
    ) -> None:
        if usage is None or usage.total_tokens == 0:
            return

        # Token-Gov: 禁止非 enum 字串寫入 usage_records（防 legacy / typo）
        if request_type not in _VALID_CATEGORIES:
            raise ValueError(
                f"request_type={request_type!r} is not a valid UsageCategory. "
                f"Valid values: {sorted(_VALID_CATEGORIES)}"
            )

        # Fallback: ReAct 路徑的 TokenUsage 可能缺少 cost，從 registry 重算
        cost = usage.estimated_cost
        if cost == 0.0 and usage.total_tokens > 0:
            cost = self._estimate_cost_from_registry(
                usage.model, usage.input_tokens, usage.output_tokens,
                usage.cache_read_tokens, usage.cache_creation_tokens,
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

        # S-Token-Gov.2: 扣 ledger（若該 category 對該租戶計入額度）
        # 包 try/except — 扣費失敗不應影響 token 記錄主流程（審計優先於計費）
        if self._deduct and self._tenant_repo:
            try:
                tenant = await self._tenant_repo.find_by_id(tenant_id)
                if tenant and self._should_count_for_quota(tenant, request_type):
                    await self._deduct.execute(
                        tenant_id=tenant_id,
                        tokens=usage.total_tokens,
                        plan_name=tenant.plan,
                    )
            except Exception:
                logger.warning(
                    "ledger.deduct_failed",
                    tenant_id=tenant_id,
                    request_type=request_type,
                    tokens=usage.total_tokens,
                    exc_info=True,
                )

    @staticmethod
    def _estimate_cost_from_registry(
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
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
        return calculate_usage(
            model, input_tokens, output_tokens, pricing,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        ).estimated_cost
