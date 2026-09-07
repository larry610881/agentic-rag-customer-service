"""記錄 Token 使用量用例 — S-Ledger-Unification P4

token_usage_records 為唯一 quota truth。每次呼叫：
1. 寫入 usage_record（append-only）
2. （選）auto-topup hook — 若額度耗盡、生效策略為 auto_topup 且 plan 支援加值，
   寫 topup 記錄

不再呼叫 DeductTokensUseCase / mutate ledger。`base_remaining` / `addon_remaining`
改由 ComputeTenantQuotaUseCase 從 SUM(usage_records) + SUM(topups) 即時算出。

Issue #74：
- 租戶方案為點數制時，記帳當下依 `domain/billing/points.py::points_for` 換算點數
  （方案 / 倍率 / 匯率走 `CachedBillingContextProvider` 60 秒快取）；token 制恆 0。
- auto-topup 分支改讀生效的 exhaustion_policy（block 不加購）；月上限由
  TopupAddonUseCase 判斷。
- 寫入後讓配額預檢快取失效。
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from src.domain.billing.exhaustion import effective_policy
from src.domain.billing.points import points_for
from src.domain.plan.entity import BillingMode, ExhaustionPolicy
from src.domain.platform.model_registry import DEFAULT_MODELS
from src.domain.rag.pricing import calculate_usage
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import DEPRECATED_CATEGORIES, UsageCategory
from src.domain.usage.entity import UsageRecord
from src.domain.usage.repository import UsageRepository

if TYPE_CHECKING:
    from src.application.billing.billing_context import (
        CachedBillingContextProvider,
        TenantBillingContext,
    )
    from src.application.billing.quota_preflight import QuotaPreflightService
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
        billing_context: "CachedBillingContextProvider | None" = None,
        quota_preflight: "QuotaPreflightService | None" = None,
    ) -> None:
        self._repo = usage_repository
        self._compute_quota = compute_quota
        self._topup_addon = topup_addon
        self._tenant_repo = tenant_repository
        self._plan_repo = plan_repository
        self._pricing_cache = pricing_cache
        self._billing_context = billing_context
        self._quota_preflight = quota_preflight

    async def execute(
        self,
        tenant_id: str,
        request_type: str,
        usage: TokenUsage | None,
        bot_id: str | None = None,
        kb_id: str | None = None,
        message_id: str | None = None,
        run_id: str | None = None,
        config_version_id: str | None = None,
        config_hash: str | None = None,
    ) -> None:
        if usage is None or usage.total_tokens == 0:
            return

        if request_type not in _VALID_CATEGORIES:
            raise ValueError(
                f"request_type={request_type!r} is not a valid UsageCategory. "
                f"Valid values: {sorted(_VALID_CATEGORIES)}"
            )
        # Issue #73：deprecated 類別只供讀取歷史紀錄，不得再產生新帳
        if request_type in DEPRECATED_CATEGORIES:
            raise ValueError(
                f"request_type={request_type!r} is deprecated and no longer "
                "accepts new usage records"
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
            reasoning_tokens=getattr(usage, "reasoning_tokens", 0) or 0,
            bot_id=bot_id,
            kb_id=kb_id,
            message_id=message_id,
            run_id=run_id,
            config_version_id=config_version_id,
            config_hash=config_hash,
        )
        record.points = await self._compute_points(record)
        await self._repo.save(record)

        # Issue #74：寫入後讓共用預檢快取失效（fail-open）
        if self._quota_preflight is not None:
            try:
                await self._quota_preflight.invalidate(tenant_id)
            except Exception:
                logger.warning("quota_preflight.invalidate_failed", tenant_id=tenant_id)

        # P4: auto-topup hook — usage 寫入後檢查是否需要續約
        # 任何失敗只 warn（審計優先於計費），不影響 usage 記錄主流程
        if (
            self._compute_quota is not None
            and self._topup_addon is not None
            and self._tenant_repo is not None
            and self._plan_repo is not None
        ):
            try:
                await self._maybe_auto_topup(tenant_id)
            except Exception:
                logger.warning(
                    "auto_topup.check_failed",
                    tenant_id=tenant_id,
                    request_type=request_type,
                    exc_info=True,
                )

    async def _compute_points(self, record: UsageRecord) -> int:
        """Issue #74：點數制方案才換算；脈絡失敗記 0 點 + warning（token 仍是事實）。"""
        if self._billing_context is None:
            return 0
        try:
            ctx: TenantBillingContext | None = (
                await self._billing_context.for_tenant(record.tenant_id)
            )
        except Exception:
            logger.warning(
                "usage.points.context_failed",
                tenant_id=record.tenant_id,
                exc_info=True,
            )
            return 0
        if ctx is None or ctx.plan is None or not ctx.is_points_mode:
            return 0
        model_points = None
        if self._pricing_cache is not None:
            model_points = self._pricing_cache.lookup_points(
                model_spec=record.model, at=datetime.now(timezone.utc)
            )
        return points_for(
            record, ctx.plan, ctx.multipliers, model_points, ctx.usd_per_point
        )

    async def _maybe_auto_topup(self, tenant_id: str) -> None:
        assert self._compute_quota and self._topup_addon
        assert self._tenant_repo and self._plan_repo
        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            return
        plan = await self._plan_repo.find_by_name(tenant.plan)
        if plan is None:
            return
        # Issue #74：生效策略為 block 時不自動加購（由預檢攔阻）。
        # getattr：plan / tenant / snapshot 可能是舊版 duck-typed 物件（無新欄位）。
        policy = effective_policy(
            getattr(plan, "exhaustion_policy", None),
            getattr(tenant, "exhaustion_policy_override", None),
        )
        if policy != ExhaustionPolicy.AUTO_TOPUP:
            return
        quota = await self._compute_quota.execute(tenant_id)
        if getattr(quota, "billing_mode", BillingMode.TOKEN) == BillingMode.POINTS:
            exhausted = quota.points_remaining <= 0
        else:
            # Token-Gov.7 D: base 和 addon 都耗盡才 topup
            exhausted = quota.base_remaining <= 0 and quota.addon_remaining <= 0
        if exhausted:
            await self._topup_addon.execute(
                tenant_id=tenant_id,
                cycle_year_month=quota.cycle_year_month,
                plan=plan,
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
