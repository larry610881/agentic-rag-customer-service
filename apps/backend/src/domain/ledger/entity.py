"""Token Ledger 月度帳本實體 — S-Token-Gov.2

每個 (tenant_id, cycle_year_month) 一筆，記錄該月的:
- base_total / base_remaining: 月度基礎額度（plan.base_monthly_tokens snapshot）
- addon_remaining: 加值包餘額（上月 carryover + Token-Gov.3 自動續約）
- total_used_in_cycle: 累計用量（即使超額也記，給 dashboard）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def current_year_month() -> str:
    """回傳當前 cycle 字串，格式 'YYYY-MM'。"""
    return datetime.now(timezone.utc).strftime("%Y-%m")


@dataclass
class TokenLedger:
    """月度帳本 — 一個 (tenant_id, cycle) 一筆。

    扣費規則：先 base 後 addon，addon 允許負數（軟上限）。
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    cycle_year_month: str = ""  # "YYYY-MM"
    plan_name: str = ""
    base_total: int = 0
    base_remaining: int = 0
    addon_remaining: int = 0  # 可為負（軟上限）
    total_used_in_cycle: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def total_remaining(self) -> int:
        """總剩餘額度（base + addon，可為負）"""
        return self.base_remaining + self.addon_remaining

    def deduct(self, tokens: int) -> None:
        """扣用順序：先 base 後 addon。允許 addon 為負（軟上限 — 不阻擋）。

        Args:
            tokens: 要扣的 token 數，<= 0 時 noop
        """
        if tokens <= 0:
            return
        self.total_used_in_cycle += tokens
        if self.base_remaining >= tokens:
            self.base_remaining -= tokens
        elif self.base_remaining > 0:
            # base 部分用完，剩下吃 addon
            remaining = tokens - self.base_remaining
            self.base_remaining = 0
            self.addon_remaining -= remaining
        else:
            # base 已用完，全吃 addon（addon 可變負）
            self.addon_remaining -= tokens
        self.updated_at = datetime.now(timezone.utc)
