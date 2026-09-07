"""配額預檢（用完即擋的共用閘門）— Issue #74

channel-parity：web / widget / LINE 三通路 + 背景任務（文件處理、評估跑批）
全部呼叫這一個 service；通路轉接器只負責把 `decision.message` 用自己的格式呈現
（web/widget 402 或 SSE `quota_exhausted` 事件、LINE 文字回覆、
文件狀態 `quota_exhausted`）。

- Redis 快取 30 秒，key `quota:pre:{tenant}`；RecordUsage 寫入後 `invalidate`。
- fail-open：Redis / DB 任一失敗 → 放行 + warning（POC 無 Redis 時退回直接查）。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

import structlog

from src.domain.billing.exhaustion import (
    REASON_DISABLED,
    REASON_FAIL_OPEN,
    REASON_NOT_BILLABLE,
    ExhaustionDecision,
    QuotaExhaustedError,
    decide,
)
from src.domain.plan.entity import BillingMode, ExhaustionPolicy

if TYPE_CHECKING:
    from src.application.quota.compute_tenant_quota_use_case import (
        ComputeTenantQuotaUseCase,
        TenantQuotaSnapshot,
    )

logger = structlog.get_logger(__name__)

CACHE_KEY_PREFIX = "quota:pre:"
DEFAULT_TTL_SECONDS = 30


def _allowed(
    reason: str, policy: str = ExhaustionPolicy.AUTO_TOPUP, remaining: int = 0
) -> ExhaustionDecision:
    return ExhaustionDecision(
        allowed=True, reason=reason, policy=policy, remaining=remaining
    )


def _snapshot_to_state(snapshot: "TenantQuotaSnapshot") -> dict[str, Any]:
    points = snapshot.billing_mode == BillingMode.POINTS
    return {
        "billing_mode": snapshot.billing_mode,
        "policy": snapshot.effective_policy,
        "remaining": snapshot.points_remaining if points else snapshot.total_remaining,
        "base_total": snapshot.points_total if points else snapshot.base_total,
        "grace_percent": float(snapshot.grace_percent),
        "message": snapshot.block_message,
        "included_categories": snapshot.included_categories,
        "category_multipliers": dict(snapshot.category_multipliers),
    }


def decide_for_category(state: dict[str, Any], category: str) -> ExhaustionDecision:
    """依快取狀態對某類別做判斷：不計入額度 / 倍率 0 的類別不受攔阻。"""
    policy = str(state.get("policy") or ExhaustionPolicy.AUTO_TOPUP)
    remaining = int(state.get("remaining") or 0)
    if state.get("billing_mode") == BillingMode.POINTS:
        multiplier = state.get("category_multipliers", {}).get(category)
        if multiplier is not None and float(multiplier) <= 0:
            return _allowed(REASON_NOT_BILLABLE, policy, remaining)
    else:
        included = state.get("included_categories")
        if included is not None and category not in included:
            return _allowed(REASON_NOT_BILLABLE, policy, remaining)
    return decide(
        policy,
        remaining,
        int(state.get("base_total") or 0),
        state.get("grace_percent") or 0,
        message=str(state.get("message") or ""),
    )


class QuotaPreflightService:
    def __init__(
        self,
        compute_quota_factory: Callable[[], "ComputeTenantQuotaUseCase"] | None,
        redis_client: Any | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._compute_quota_factory = compute_quota_factory
        self._redis = redis_client
        self._ttl = ttl_seconds

    @staticmethod
    def cache_key(tenant_id: str) -> str:
        return f"{CACHE_KEY_PREFIX}{tenant_id}"

    async def check(self, tenant_id: str, category: str) -> ExhaustionDecision:
        if self._compute_quota_factory is None:
            return _allowed(REASON_DISABLED)
        try:
            state = await self._load_state(tenant_id)
        except Exception:
            logger.warning(
                "quota_preflight.fail_open", tenant_id=tenant_id,
                category=category, exc_info=True,
            )
            return _allowed(REASON_FAIL_OPEN)
        decision = decide_for_category(state, category)
        if not decision.allowed:
            logger.info(
                "quota_preflight.blocked", tenant_id=tenant_id,
                category=category, policy=decision.policy,
                remaining=decision.remaining,
            )
        return decision

    async def ensure_allowed(self, tenant_id: str, category: str) -> ExhaustionDecision:
        """被擋時 raise `QuotaExhaustedError`（web/widget 402、背景任務同一錯誤）。"""
        decision = await self.check(tenant_id, category)
        if not decision.allowed:
            raise QuotaExhaustedError(decision.message, decision)
        return decision

    async def invalidate(self, tenant_id: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(self.cache_key(tenant_id))
        except Exception:
            logger.warning("quota_preflight.invalidate_failed", tenant_id=tenant_id)

    async def _load_state(self, tenant_id: str) -> dict[str, Any]:
        key = self.cache_key(tenant_id)
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
            except Exception:
                logger.warning(
                    "quota_preflight.cache_read_failed", tenant_id=tenant_id
                )
                raw = None
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                cached: dict[str, Any] = json.loads(raw)
                return cached

        assert self._compute_quota_factory is not None
        snapshot = await self._compute_quota_factory().execute(tenant_id)
        state = _snapshot_to_state(snapshot)

        if self._redis is not None:
            try:
                await self._redis.set(key, json.dumps(state), ex=self._ttl)
            except Exception:
                logger.warning(
                    "quota_preflight.cache_write_failed", tenant_id=tenant_id
                )
        return state
