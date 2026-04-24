"""TokenLedgerTopup Repository ABC — S-Ledger-Unification P1"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ledger.topup_entity import TokenLedgerTopup


class TokenLedgerTopupRepository(ABC):
    @abstractmethod
    async def save(self, topup: TokenLedgerTopup) -> TokenLedgerTopup:
        """append-only — 每筆都是新增，不覆寫。"""
        ...

    @abstractmethod
    async def sum_amount_in_cycle(
        self, tenant_id: str, cycle_year_month: str
    ) -> int:
        """SUM(amount) for (tenant, cycle). Return 0 if no records."""
        ...

    @abstractmethod
    async def find_in_cycle(
        self, tenant_id: str, cycle_year_month: str
    ) -> list[TokenLedgerTopup]:
        """列出該月所有 topup 紀錄（供審計用）。"""
        ...
