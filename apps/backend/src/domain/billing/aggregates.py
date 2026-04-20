"""Billing aggregates — S-Token-Gov.4

純值物件 — 從 BillingTransactionRepository 的聚合 query 回傳，
給 GetBillingDashboardUseCase 組合儀表板用。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MonthlyRevenuePoint:
    """月營收時間序列的一筆。"""
    cycle_year_month: str
    total_amount: Decimal
    transaction_count: int
    addon_tokens_total: int  # 該月所有 auto_topup 加總的 token 數


@dataclass(frozen=True)
class PlanRevenuePoint:
    """單一 plan 在範圍內的營收貢獻。"""
    plan_name: str
    total_amount: Decimal
    transaction_count: int


@dataclass(frozen=True)
class TenantRevenuePoint:
    """單一 tenant 的營收（不含 tenant_name；application 層補）"""
    tenant_id: str
    total_amount: Decimal
    transaction_count: int
