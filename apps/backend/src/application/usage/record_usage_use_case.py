"""記錄 Token 使用量用例 — S-Ledger-Unification P4

token_usage_records 為唯一 quota truth。每次呼叫：
1. 寫入 usage_record（append-only）
2. （選）auto-topup hook — 若 base + addon 都耗盡且 plan 支援加值，寫 topup 記錄

不再呼叫 DeductTokensUseCase / mutate ledger。`base_remaining` / `addon_remaining`
改由 ComputeTenantQuotaUseCase 從 SUM(usage_records) + SUM(topups) 即時算出。
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from src.domain.platform.model_registry import DEFAULT_MODELS
from src.domain.rag.pricing import calculate_usage
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import UsageCategory
from src.domain.usage.entity import UsageRecord
from src.domain.usage.repository import UsageRepository

if TYPE_CHECKING:
    from src.application.billing.topup_addon_use_case import TopupAddonUseCase
    from src.application.quota.compute_tenant_quota_use_case import (
        ComputeTenantQuotaUseCase,
    )
    from src.domain.plan.repository import PlanRepository
    from src.domain.tenant.repository import TenantRepository
    from src.infrastructure.pricing.pricing_cache import InMemoryPricingCache

logger = structlog.get_logger(__name__)

_VALID_CATEGORIES: frozenset[str] = frozenset(c.value for c in UsageCategory)


class RecordUsageUseCase:
    def __init__(
        self,
        usage_repository: UsageRepository,
        compute_quota: "ComputeTenantQuotaUseCase | None" = None,
        topup_addon: "TopupAddonUseCase | None" = None,
        tenant_repository: "TenantRepository | None" = None,
        plan_repository: "PlanRepository | None" = None,
        pricing_cache: "InMemoryPricingCache | None" = None,
    ) -> None:
        self._repo = usage_repository
        self._compute_quota = compute_quota
        self._topup_addon = topup_addon
        self._tenant_repo = tenant_repository
        self._plan_repo = plan_repository
        self._pricing_cache = pricing_cache

    async def execute(
        self,
        tenant_id: str,
        request_type: str,
        usage: TokenUsage | None,
        bot_id: str | None = None,
        kb_id: str | None = None,
        message_id: str | None = None,
    ) -> None:
        if usage is None or usage.total_tokens == 0:
            return

        if request_type not in _VALID_CATEGORIES:
            raise ValueError(
                f"request_type={request_type!r} is not a valid UsageCategory. "
                f"Valid values: {sorted(_VALID_CATEGORIES)}"
            )

        cost = usage.estimated_cost
        if cost == 0.0 and usage.total_tokens > 0:
            cost = self._estimate_cost(
                usage.model, usage.input_tokens, usage.output_tokens,
                usage.cache_read_tokens, usage.cache_creation_tokens,
            )

        record = UsageRecord(
            tenant_id=tenant_id,
            request_type=request_type,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost=cost,
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            bot_id=bot_id,
            kb_id=kb_id,
            message_id=message_id,
        )
        await self._repo.save(record)

        # P4: auto-topup hook — usage 寫入後檢查是否需要續約
        # 任何失敗只 warn（審計優先於計費），不影響 usage 記錄主流程
        if (
            self._compute_quota is not None
            and self._topup_addon is not None
            and self._tenant_repo is not None
            and self._plan_repo is not None
        ):
            try:
                tenant = await self._tenant_repo.find_by_id(tenant_id)
                if tenant is None:
                    return
                quota = await self._compute_quota.execute(tenant_id)
                # Token-Gov.7 D: base 和 addon 都耗盡才 topup
                if quota.base_remaining <= 0 and quota.addon_remaining <= 0:
                    plan = await self._plan_repo.find_by_name(tenant.plan)
                    if plan is not None:
                        await self._topup_addon.execute(
                            tenant_id=tenant_id,
                            cycle_year_month=quota.cycle_year_month,
                            plan=plan,
                        )
            except Exception:
                logger.warning(
                    "auto_topup.check_failed",
                    tenant_id=tenant_id,
                    request_type=request_type,
                    exc_info=True,
                )

    def _estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        if self._pricing_cache is not None:
            rate = self._pricing_cache.lookup(
                model_spec=model, at=datetime.now(timezone.utc)
            )
            if rate is not None:
                lookup_model = model.split(":", 1)[1] if ":" in model else model
                pricing_dict = {lookup_model: rate}
                return calculate_usage(
                    lookup_model, input_tokens, output_tokens, pricing_dict,
                    cache_read_tokens=cache_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                ).estimated_cost

        return self._estimate_cost_from_registry(
            model, input_tokens, output_tokens,
            cache_read_tokens, cache_creation_tokens,
        )

    @staticmethod
    def _estimate_cost_from_registry(
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
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

        lookup_model = model.split(":", 1)[1] if ":" in model else model

        return calculate_usage(
            lookup_model, input_tokens, output_tokens, pricing,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        ).estimated_cost
