"""Plan 限界上下文 — 方案模板實體

S-Token-Gov.1：方案模板提供月度基礎額度 + 加值包配置，
後續 Token-Gov.2 ledger 從此讀取扣費基準。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4


@dataclass
class Plan:
    """方案模板。

    name 是 Tenant.plan 字串 FK 的目標 — 唯一鍵，不可改名（要改就刪除重建）。
    `is_active=False` 為軟刪：仍可被既有租戶綁定，但新建 / 換 plan 時不可選。
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    base_monthly_tokens: int = 0
    addon_pack_tokens: int = 0
    base_price: Decimal = field(default_factory=lambda: Decimal("0"))
    addon_price: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "TWD"
    description: str | None = None
    is_active: bool = True
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
