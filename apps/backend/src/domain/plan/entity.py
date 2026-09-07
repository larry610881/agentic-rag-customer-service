"""Plan 限界上下文 — 方案模板實體

S-Token-Gov.1：方案模板提供月度基礎額度 + 加值包配置，
後續 Token-Gov.2 ledger 從此讀取扣費基準。

Issue #74：雙軌計價 + 額度用盡策略。
- `billing_mode`：token（預設，維持現行）或 points（月費 + 月點數 + 類別倍率）。
  token 永遠是事實來源，點數是記帳當下的換算層。
- `exhaustion_policy`：額度用盡後自動展延（auto_topup）或用完即擋（block），
  **獨立於計價模式**；`tenant_may_change_policy` 決定租戶能否自改。
- 月費沿用 `base_price`（待決 Q3 定案：不另加 monthly_price）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from src.domain.shared.exceptions import DomainException


class BillingMode:
    TOKEN = "token"
    POINTS = "points"
    ALL: frozenset[str] = frozenset({TOKEN, POINTS})


class ExhaustionPolicy:
    AUTO_TOPUP = "auto_topup"
    BLOCK = "block"
    ALL: frozenset[str] = frozenset({AUTO_TOPUP, BLOCK})


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
    # Issue #74 — 雙軌計價
    billing_mode: str = BillingMode.TOKEN
    monthly_points: int = 0
    addon_pack_points: int = 0
    default_category_multiplier: Decimal = field(
        default_factory=lambda: Decimal("1")
    )
    # Issue #74 — 額度用盡策略（獨立於計價模式）
    exhaustion_policy: str = ExhaustionPolicy.AUTO_TOPUP
    tenant_may_change_policy: bool = False
    auto_topup_monthly_cap: int = 0  # 0 = 不限
    grace_percent: Decimal = field(default_factory=lambda: Decimal("0"))
    block_message: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_points_mode(self) -> bool:
        return self.billing_mode == BillingMode.POINTS

    def validate_billing(self) -> None:
        """Issue #74 欄位範圍檢查；違反拋 DomainException（router 對應 400）。"""
        if self.billing_mode not in BillingMode.ALL:
            raise DomainException(
                f"billing_mode must be one of {sorted(BillingMode.ALL)}"
            )
        if self.exhaustion_policy not in ExhaustionPolicy.ALL:
            raise DomainException(
                f"exhaustion_policy must be one of {sorted(ExhaustionPolicy.ALL)}"
            )
        if self.monthly_points < 0 or self.addon_pack_points < 0:
            raise DomainException("Point counts must be >= 0")
        if self.default_category_multiplier < 0:
            raise DomainException("default_category_multiplier must be >= 0")
        if self.auto_topup_monthly_cap < 0:
            raise DomainException("auto_topup_monthly_cap must be >= 0")
        if not (Decimal("0") <= self.grace_percent <= Decimal("100")):
            raise DomainException("grace_percent must be between 0 and 100")
