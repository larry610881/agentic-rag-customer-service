"""BillingTransaction Repository ABC"""

from __future__ import annotations

from abc import ABC, abstractmethod

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
