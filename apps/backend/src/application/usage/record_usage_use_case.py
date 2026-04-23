"""記錄 Token 使用量用例"""

from datetime import datetime, timezone
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
    from src.infrastructure.pricing.pricing_cache import InMemoryPricingCache

logger = structlog.get_logger(__name__)

# Token-Gov: request_type 白名單 — 只接受 UsageCategory enum 值，擋掉 legacy 字串與 typo
_VALID_CATEGORIES: frozenset[str] = frozenset(c.value for c in UsageCategory)


class RecordUsageUseCase:
    def __init__(
        self,
        usage_repository: UsageRepository,
        deduct_tokens: "DeductTokensUseCase | None" = None,
        tenant_repository: "TenantRepository | None" = None,
        pricing_cache: "InMemoryPricingCache | None" = None,
    ) -> None:
        self._repo = usage_repository
        # S-Token-Gov.2: 注入後會在每筆 usage 寫入後扣 ledger
        self._deduct = deduct_tokens
        self._tenant_repo = tenant_repository
        # S-Pricing.1: 先查 DB-backed pricing cache，miss 時 fallback 到 DEFAULT_MODELS
        self._pricing_cache = pricing_cache

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
        kb_id: str | None = None,
        message_id: str | None = None,
    ) -> None:
        if usage is None or usage.total_tokens == 0:
            return

        # Token-Gov: 禁止非 enum 字串寫入 usage_records（防 legacy / typo）
        if request_type not in _VALID_CATEGORIES:
            raise ValueError(
                f"request_type={request_type!r} is not a valid UsageCategory. "
                f"Valid values: {sorted(_VALID_CATEGORIES)}"
            )

        # Fallback: ReAct 路徑的 TokenUsage 可能缺少 cost，從 cache / registry 重算
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
            # Token-Gov.6: total_tokens 是 @property (= input + output + cache_*)，
            # 不再從 TokenUsage 帶入。Provider SDK 的 total_tokens 值被此處捨棄
            # — 若與 computed 不同只會有幾個 token 差距，不影響計費正確性。
            estimated_cost=cost,
            cache_read_tokens=usage.cache_read_tokens,
            cache_creation_tokens=usage.cache_creation_tokens,
            bot_id=bot_id,
            kb_id=kb_id,
            message_id=message_id,
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

    def _estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """計算 estimated_cost：先查 DB PricingCache，miss 時 fallback DEFAULT_MODELS。

        S-Pricing.1：admin 透過 UI 改價 → 寫入 DB → PricingCache.refresh() 後
        hot path 立即用新價。DB 空或 model 不在 cache 時走 DEFAULT_MODELS，避免
        estimated_cost=0（S-LLM-Cache.2 fix）。
        """
        # 1. 先查 cache（DB-backed）
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

        # 2. Fallback DEFAULT_MODELS
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
        """從 DEFAULT_MODELS registry 查定價（PricingCache miss 時 fallback）。

        S-LLM-Cache.2 fix：model 可能帶 `provider:` 前綴（例 "litellm:azure_ai/..."），
        pricing dict key 是裸 model_id → lookup 前先 normalize 去前綴。支援兩種格式。
        """
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

        # 去除 provider 前綴：call_llm 經 _parse_model_spec 後 LLMCallResult.model
        # 是裸 id，但 service 層累計的 last_model 保留 full spec（含前綴）。兩種 case
        # 都要能查到 pricing。
        lookup_model = model.split(":", 1)[1] if ":" in model else model

        return calculate_usage(
            lookup_model, input_tokens, output_tokens, pricing,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        ).estimated_cost
