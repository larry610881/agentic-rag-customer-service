"""TokenLedgerTopup Entity — S-Ledger-Unification P1

Append-only log of addon topups per (tenant, cycle). 取代
token_ledgers.addon_remaining mutable 欄位。addon_remaining 由
ComputeTenantQuotaUseCase 從 SUM(topups) - overage 算出。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

REASON_AUTO_TOPUP = "auto_topup"
REASON_MANUAL_ADJUST = "manual_adjust"
REASON_CARRYOVER = "carryover"

VALID_REASONS = frozenset(
    {REASON_AUTO_TOPUP, REASON_MANUAL_ADJUST, REASON_CARRYOVER}
)


@dataclass(frozen=True)
class TokenLedgerTopup:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    cycle_year_month: str = ""  # "YYYY-MM"
    amount: int = 0  # 正=加值，負=退款/手動扣
    reason: str = REASON_AUTO_TOPUP
    pricing_version: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if self.reason not in VALID_REASONS:
            raise ValueError(
                f"reason={self.reason!r} must be one of {sorted(VALID_REASONS)}"
            )
