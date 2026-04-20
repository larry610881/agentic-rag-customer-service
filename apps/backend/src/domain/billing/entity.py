"""Billing 限界上下文 — 自動續約交易紀錄 + 額度警示 (S-Token-Gov.3)

兩個 entity 都是 append-only event log：
- BillingTransaction: 自動續約成功時寫入，含金額 snapshot（plan 改價歷史不變）
- QuotaAlertLog: 80% / 100% 門檻觸發時寫入，per cycle 每 alert_type 至多一筆
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4


# Transaction types — 預留 manual_topup / refund 給未來
TRANSACTION_TYPE_AUTO_TOPUP = "auto_topup"

# Triggered by
TRIGGERED_BY_SYSTEM = "system"
TRIGGERED_BY_ADMIN = "admin"


@dataclass
class BillingTransaction:
    """自動續約交易紀錄（會計事件）。

    snapshot 欄位（plan_name / amount_currency / amount_value）— plan 後改名
    或改價時，已寫入的歷史 transaction 不受影響。
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    ledger_id: str = ""
    cycle_year_month: str = ""  # snapshot of ledger.cycle_year_month
    plan_name: str = ""  # snapshot
    transaction_type: str = TRANSACTION_TYPE_AUTO_TOPUP
    addon_tokens_added: int = 0
    amount_currency: str = "TWD"  # snapshot from plan.currency
    amount_value: Decimal = field(default_factory=lambda: Decimal("0"))  # snapshot from plan.addon_price
    triggered_by: str = TRIGGERED_BY_SYSTEM  # 'system' | 'admin'
    reason: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
