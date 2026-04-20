"""BillingTransaction Repository ABC"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.billing.aggregates import (
    MonthlyRevenuePoint,
    PlanRevenuePoint,
    TenantRevenuePoint,
)
from src.domain.billing.entity import BillingTransaction


class BillingTransactionRepository(ABC):
    @abstractmethod
    async def save(self, tx: BillingTransaction) -> BillingTransaction:
        """新增（append-only — 不更新既有 row）"""
        ...

    @abstractmethod
    async def find_by_tenant_and_cycle(
        self, tenant_id: str, cycle: str
    ) -> list[BillingTransaction]:
        """測試 + tenant 自助頁用 — 該租戶該月所有交易，按時間升序。"""
        ...

    @abstractmethod
    async def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[BillingTransaction]:
        """admin 列表：跨租戶或單租戶，按 created_at desc。"""
        ...

    @abstractmethod
    async def count_recent(
        self, tenant_id: str | None = None
    ) -> int: ...

    # --- S-Token-Gov.4: Aggregations ---

    @abstractmethod
    async def aggregate_monthly_revenue(
        self,
        *,
        start_cycle: str,
        end_cycle: str,
        tenant_id: str | None = None,
    ) -> list[MonthlyRevenuePoint]:
        """按 cycle_year_month group by + sum amount_value，回傳時間序列（升序）。"""
        ...

    @abstractmethod
    async def aggregate_by_plan(
        self,
        *,
        start_cycle: str,
        end_cycle: str,
    ) -> list[PlanRevenuePoint]:
        """按 plan_name group by + sum + count，按 total_amount desc。"""
        ...

    @abstractmethod
    async def aggregate_top_tenants(
        self,
        *,
        start_cycle: str,
        end_cycle: str,
        limit: int = 10,
    ) -> list[TenantRevenuePoint]:
        """按 tenant_id group by + sum + count，order by sum desc，limit N。"""
        ...
