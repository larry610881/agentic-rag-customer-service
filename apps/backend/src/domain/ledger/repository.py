"""TokenLedger Repository ABC"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ledger.entity import TokenLedger


class TokenLedgerRepository(ABC):
    @abstractmethod
    async def save(self, ledger: TokenLedger) -> TokenLedger:
        """新增或更新（依 id upsert）"""
        ...

    @abstractmethod
    async def find_by_tenant_and_cycle(
        self, tenant_id: str, cycle: str
    ) -> TokenLedger | None: ...

    @abstractmethod
    async def find_latest_by_tenant(
        self, tenant_id: str
    ) -> TokenLedger | None:
        """最近一筆 — cron 月度重置時讀上月 addon_remaining 做 carryover。"""
        ...

    @abstractmethod
    async def find_all_for_cycle(self, cycle: str) -> list[TokenLedger]:
        """某個月所有租戶的 ledger — 給收益儀表板（Token-Gov.4）用。"""
        ...
