"""額度用盡策略 — Issue #74

策略獨立於計價模式：
- `auto_topup`：額度用盡自動加購（受方案月上限），永遠放行。
- `block`：用完即擋；可設寬限百分比（以月基礎額度計）。

`decide` 是純函式；`QuotaPreflightService`（application）負責查配額 / 快取，
三通路與背景任務共用同一份判斷（channel-parity）。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.domain.plan.entity import ExhaustionPolicy
from src.domain.shared.exceptions import DomainException

DEFAULT_BLOCK_MESSAGE = "本月額度已用完，服務暫停。請聯繫管理員加購額度或等待下月重置。"

REASON_AUTO_TOPUP = "auto_topup"
REASON_WITHIN_QUOTA = "within_quota"
REASON_GRACE = "grace"
REASON_EXHAUSTED = "exhausted"
REASON_NOT_BILLABLE = "not_billable"
REASON_FAIL_OPEN = "fail_open"
REASON_DISABLED = "disabled"


@dataclass(frozen=True)
class ExhaustionDecision:
    allowed: bool
    reason: str
    policy: str
    remaining: int
    grace_applied: bool = False
    message: str = ""


def allow(
    reason: str, policy: str = ExhaustionPolicy.AUTO_TOPUP, remaining: int = 0
) -> ExhaustionDecision:
    return ExhaustionDecision(
        allowed=True, reason=reason, policy=policy, remaining=remaining
    )


def effective_policy(plan_policy: str | None, tenant_override: str | None) -> str:
    """租戶覆寫 → 方案預設 → 平台預設（auto_topup，既有租戶行為不變）。"""
    for candidate in (tenant_override, plan_policy):
        if candidate in ExhaustionPolicy.ALL:
            return candidate  # type: ignore[return-value]
    return ExhaustionPolicy.AUTO_TOPUP


def resolve_block_message(
    tenant_override: str | None, plan_message: str | None
) -> str:
    """被擋文案：租戶覆寫 → 方案 → 平台預設常數（待決 Q5 定案）。"""
    for candidate in (tenant_override, plan_message):
        if candidate and candidate.strip():
            return candidate.strip()
    return DEFAULT_BLOCK_MESSAGE


def decide(
    policy: str,
    remaining: int,
    base_total: int,
    grace_percent: Decimal | float | int = 0,
    message: str = "",
) -> ExhaustionDecision:
    if policy != ExhaustionPolicy.BLOCK:
        return ExhaustionDecision(
            allowed=True, reason=REASON_AUTO_TOPUP,
            policy=ExhaustionPolicy.AUTO_TOPUP, remaining=remaining,
        )
    if remaining > 0:
        return ExhaustionDecision(
            allowed=True, reason=REASON_WITHIN_QUOTA,
            policy=policy, remaining=remaining,
        )
    grace = Decimal(max(base_total, 0)) * Decimal(str(grace_percent)) / Decimal(100)
    if grace > 0 and Decimal(remaining) + grace > 0:
        return ExhaustionDecision(
            allowed=True, reason=REASON_GRACE, policy=policy,
            remaining=remaining, grace_applied=True,
        )
    return ExhaustionDecision(
        allowed=False, reason=REASON_EXHAUSTED, policy=policy,
        remaining=remaining, message=message or DEFAULT_BLOCK_MESSAGE,
    )


class QuotaExhaustedError(DomainException):
    """用完即擋：三通路 / 背景任務共用。router 對應 402 quota_exhausted。"""

    def __init__(
        self,
        message: str = DEFAULT_BLOCK_MESSAGE,
        decision: ExhaustionDecision | None = None,
    ) -> None:
        super().__init__(message or DEFAULT_BLOCK_MESSAGE)
        self.decision = decision
