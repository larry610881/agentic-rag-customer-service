"""租戶計價脈絡（方案 / 倍率表 / 平台匯率）快取 — Issue #74

RecordUsageUseCase 每筆記帳都要知道租戶方案的計價模式與倍率；
ComputeTenantQuotaUseCase / QuotaPreflightService 要知道模式與用盡策略。
三者共用這一份程序內快取（60 秒），寫入方案 / 倍率 / 匯率 / 租戶策略時
失效。

模式對齊 `CachedAbusePolicyProvider`：Singleton + repo factory
（`.provider` delegation），不持有 session。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

import structlog

from src.domain.billing.exhaustion import effective_policy, resolve_block_message
from src.domain.billing.points import multiplier_for
from src.domain.billing.settings import DEFAULT_USD_PER_POINT, BillingSettings
from src.domain.plan.entity import BillingMode, Plan
from src.domain.tenant.entity import Tenant

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TenantBillingContext:
    tenant: Tenant
    plan: Plan | None
    multipliers: dict[str, Decimal] = field(default_factory=dict)
    usd_per_point: Decimal = DEFAULT_USD_PER_POINT

    @property
    def billing_mode(self) -> str:
        return self.plan.billing_mode if self.plan else BillingMode.TOKEN

    @property
    def is_points_mode(self) -> bool:
        return self.billing_mode == BillingMode.POINTS

    @property
    def effective_policy(self) -> str:
        return effective_policy(
            self.plan.exhaustion_policy if self.plan else None,
            self.tenant.exhaustion_policy_override,
        )

    @property
    def block_message(self) -> str:
        return resolve_block_message(
            self.tenant.block_message_override,
            self.plan.block_message if self.plan else None,
        )

    def multiplier_for(self, category: str) -> Decimal:
        if self.plan is None:
            return Decimal("1")
        return multiplier_for(self.plan, self.multipliers, category)

    def multipliers_view(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.multipliers.items()}


class CachedBillingContextProvider:
    def __init__(
        self,
        tenant_repo_factory: Callable[[], Any],
        plan_repo_factory: Callable[[], Any],
        multiplier_repo_factory: Callable[[], Any] | None = None,
        settings_repo_factory: Callable[[], Any] | None = None,
        ttl_seconds: int = 60,
    ) -> None:
        self._tenant_repo_factory = tenant_repo_factory
        self._plan_repo_factory = plan_repo_factory
        self._multiplier_repo_factory = multiplier_repo_factory
        self._settings_repo_factory = settings_repo_factory
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[TenantBillingContext | None, float]] = {}

    def invalidate(self, tenant_id: str | None = None) -> None:
        if tenant_id is None:
            self._cache.clear()
        else:
            self._cache.pop(tenant_id, None)

    async def for_tenant(self, tenant_id: str) -> TenantBillingContext | None:
        """回傳脈絡；租戶不存在回 None。DB 失敗會 raise（呼叫端決定 fail-open）。"""
        cached = self._cache.get(tenant_id)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        ctx = await self._load(tenant_id)
        self._cache[tenant_id] = (ctx, time.monotonic() + self._ttl)
        return ctx

    async def _load(self, tenant_id: str) -> TenantBillingContext | None:
        tenant = await self._tenant_repo_factory().find_by_id(tenant_id)
        if tenant is None:
            return None
        plan: Plan | None = await self._plan_repo_factory().find_by_name(tenant.plan)

        multipliers: dict[str, Decimal] = {}
        if plan is not None and self._multiplier_repo_factory is not None:
            rows = await self._multiplier_repo_factory().list_for_plan(plan.id)
            multipliers = {r.usage_category: Decimal(r.multiplier) for r in rows}

        usd_per_point = DEFAULT_USD_PER_POINT
        if self._settings_repo_factory is not None:
            settings: BillingSettings | None = await self._settings_repo_factory().get()
            if settings is not None and settings.usd_per_point > 0:
                usd_per_point = Decimal(settings.usd_per_point)

        return TenantBillingContext(
            tenant=tenant, plan=plan, multipliers=multipliers,
            usd_per_point=usd_per_point,
        )
