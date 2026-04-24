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

    # S-Ledger-Unification P7: deduct() 方法已移除
    # base/addon 餘額改由 ComputeTenantQuotaUseCase 從
    # token_usage_records + token_ledger_topups 即時算出，不再 mutate ledger。
