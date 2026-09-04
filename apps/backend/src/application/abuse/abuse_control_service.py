"""AbuseControlService（Issue #68 P7a）— 三通路共用的異常控管服務

進入回合前 `evaluate()` 決定模式（L1 保守 / L2 固定文案 / L3+ 拒絕）；
回合中 Guard / 分類器結果出來後 `record()` 加分並視需要升級。
儲存失效一律 fail-open（放行、記 log）。升級寫 AuditRecorder。
"""

from collections.abc import Callable
from typing import Any

import structlog

from src.domain.abuse.policy import (
    CONSERVATIVE_PROMPT_SUFFIX,
    NO_ABUSE,
    AbuseDecision,
    AbuseLevel,
    AbuseMode,
    AbusePolicy,
    AbuseSignal,
    AbuseSubject,
)
from src.domain.abuse.store import AbuseScoreStore
from src.domain.shared.exceptions import DomainException

logger = structlog.get_logger(__name__)

AUDIT_ENTITY = "abuse_control"
PolicyProvider = Callable[[str], AbusePolicy]


class AbuseBlockedError(DomainException):
    """主體處於 L3+：chat 拒絕。body 只給 temporarily_unavailable + retry_after。"""

    def __init__(self, retry_after: int, level: AbuseLevel) -> None:
        super().__init__("temporarily_unavailable")
        self.retry_after = max(1, int(retry_after))
        self.level = level


def apply_conservative_mode(bot_cfg: dict[str, Any]) -> dict[str, Any]:
    """L1：該回合不呼叫工具 / MCP、檢索 top-k 減半、系統提示加固定婉拒指令。"""
    bot_cfg["enabled_tools"] = []
    bot_cfg["mcp_servers"] = []
    top_k = bot_cfg.get("rag_top_k")
    if isinstance(top_k, int) and top_k > 1:
        bot_cfg["rag_top_k"] = max(1, top_k // 2)
    prompt = bot_cfg.get("system_prompt") or ""
    if CONSERVATIVE_PROMPT_SUFFIX not in prompt:
        bot_cfg["system_prompt"] = prompt + CONSERVATIVE_PROMPT_SUFFIX
    bot_cfg["_abuse_conservative"] = True
    return bot_cfg


class AbuseControlService:
    def __init__(
        self,
        store: AbuseScoreStore,
        policy: AbusePolicy | PolicyProvider,
        audit: Any | None = None,
        enabled: bool = True,
        alerts: Any | None = None,
    ) -> None:
        self._store = store
        self._policy = policy
        self._audit = audit
        self._enabled = enabled
        # Issue #68 P7c：L3+/fail-open/突增 告警（AbuseAlertService，永不拋例外）
        self._alerts = alerts

    def policy_for(self, tenant_id: str) -> AbusePolicy:
        if callable(self._policy):
            return self._policy(tenant_id)
        return self._policy

    # ------------------------------------------------------------------ read

    async def evaluate(self, tenant_id: str, subject: AbuseSubject) -> AbuseDecision:
        """回合開始前：目前等級（鎖優先，其次由分數推算）。失效 → 放行。"""
        if not self._enabled:
            return NO_ABUSE
        policy = self.policy_for(tenant_id)
        key = subject.key(tenant_id)
        try:
            locked = await self._store.get_level(key)
            if locked is not None and locked[0] > 0:
                return self._decision(
                    policy, AbuseLevel(locked[0]), retry_after=locked[1]
                )
            score = await self._store.get_score(key, policy.decay_per_minute)
        except Exception:
            logger.warning("abuse_control.store_unavailable", op="evaluate", key=key)
            await self._alert_fail_open(tenant_id, "evaluate")
            return NO_ABUSE
        level = policy.level_for(score, subject.kind)
        return self._decision(policy, level, score=score)

    # ----------------------------------------------------------------- write

    async def record(
        self,
        tenant_id: str,
        subject: AbuseSubject,
        *,
        guard_hit: bool = False,
        attack: bool = False,
        unrouted: bool = False,
        origin_mismatch: bool = False,
        identify_fail: bool = False,
        channel: str = "",
    ) -> AbuseDecision:
        """回合結束（或訊號發生）時加分；跨門檻即升級並寫稽核。失效 → 放行。"""
        if not self._enabled:
            return NO_ABUSE
        policy = self.policy_for(tenant_id)
        key = subject.key(tenant_id)
        signals: list[AbuseSignal] = [
            sig for sig, hit in (
                (AbuseSignal.GUARD_HIT, guard_hit),
                (AbuseSignal.ATTACK, attack),
                (AbuseSignal.ORIGIN_MISMATCH, origin_mismatch),
                (AbuseSignal.IDENTIFY_FAIL, identify_fail),
            ) if hit
        ]
        try:
            signals.extend(await self._behavioral_signals(key, policy, unrouted))
            delta = sum(policy.weight(s) for s in signals)
            score = await self._store.add_score(
                key, delta, policy.decay_per_minute, policy.score_ttl_seconds
            )
            new_level = policy.level_for(score, subject.kind)
            locked = await self._store.get_level(key)
            current = AbuseLevel(locked[0]) if locked else AbuseLevel.NONE
            if new_level > current:
                duration = policy.duration_for(new_level)
                await self._store.set_level(key, int(new_level), duration)
                await self._audit_escalation(
                    tenant_id, subject, current, new_level, score, signals, channel,
                    duration,
                )
                return self._decision(
                    policy, new_level, retry_after=duration, score=score,
                    reasons=tuple(s.value for s in signals),
                )
            if locked:
                return self._decision(
                    policy, current, retry_after=locked[1], score=score,
                    reasons=tuple(s.value for s in signals),
                )
            return self._decision(
                policy, new_level, score=score, reasons=tuple(s.value for s in signals)
            )
        except Exception:
            logger.warning(
                "abuse_control.store_unavailable", op="record", key=key,
                signals=[s.value for s in signals],
            )
            await self._alert_fail_open(tenant_id, "record")
            return NO_ABUSE

    async def release(
        self, tenant_id: str, subject: AbuseSubject, *, actor_user_id: str | None
    ) -> None:
        key = subject.key(tenant_id)
        await self._store.clear(key)
        await self._store.reset_counter(f"{key}:unrouted")
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY, entity_id=key, action="release",
                before={"level": "locked"}, after={"level": 0},
                actor_user_id=actor_user_id, tenant_id=tenant_id,
            )

    # --------------------------------------------------------------- helpers

    async def _behavioral_signals(
        self, key: str, policy: AbusePolicy, unrouted: bool
    ) -> list[AbuseSignal]:
        """節奏異常 + 連續無法分流（需要計數器的兩種訊號）。"""
        found: list[AbuseSignal] = []
        if await self._pacing_exceeded(key, policy):
            found.append(AbuseSignal.PACING)
        if unrouted:
            streak = await self._store.incr_counter(f"{key}:unrouted", 600)
            if streak > policy.unrouted_free_count:
                found.append(AbuseSignal.UNROUTED)
        else:
            await self._store.reset_counter(f"{key}:unrouted")
        return found

    async def _pacing_exceeded(self, key: str, policy: AbusePolicy) -> bool:
        count = await self._store.incr_counter(f"{key}:rpm", 60)
        if count <= policy.pacing_max_per_minute:
            return False
        # 每分鐘只計一次節奏異常
        flagged = await self._store.incr_counter(f"{key}:pacing_flag", 60)
        return flagged == 1

    def _decision(
        self,
        policy: AbusePolicy,
        level: AbuseLevel,
        *,
        retry_after: int = 0,
        score: float = 0.0,
        reasons: tuple[str, ...] = (),
    ) -> AbuseDecision:
        if level == AbuseLevel.NONE:
            return AbuseDecision(
                level=level, enforce=True, score=score, reasons=reasons
            )
        return AbuseDecision(
            level=level,
            enforce=policy.mode == AbuseMode.ENFORCE,
            retry_after=retry_after or policy.duration_for(level),
            score=score,
            reasons=reasons,
        )

    async def _audit_escalation(
        self,
        tenant_id: str,
        subject: AbuseSubject,
        before: AbuseLevel,
        after: AbuseLevel,
        score: float,
        signals: list[AbuseSignal],
        channel: str,
        policy_duration: int = 0,
    ) -> None:
        logger.warning(
            "abuse_control.escalated",
            tenant_id=tenant_id,
            subject_kind=subject.kind.value,
            subject_id=subject.id,
            level=int(after),
            score=round(score, 1),
            signals=[s.value for s in signals],
            channel=channel,
        )
        if self._alerts is not None:
            try:
                await self._alerts.escalated(
                    tenant_id, subject, after,
                    reasons=tuple(s.value for s in signals),
                    retry_after=policy_duration,
                    channel=channel,
                )
            except Exception:
                logger.warning("abuse_control.alert_failed", exc_info=True)
        if self._audit is None:
            return
        try:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=subject.key(tenant_id),
                action="escalate",
                before={"level": int(before)},
                after={
                    "level": int(after),
                    "score": round(score, 1),
                    "signals": [s.value for s in signals],
                    "channel": channel,
                },
                actor_user_id=None,
                tenant_id=tenant_id,
            )
        except Exception:
            logger.warning("abuse_control.audit_failed", exc_info=True)

    async def _alert_fail_open(self, tenant_id: str, op: str) -> None:
        if self._alerts is None:
            return
        try:
            await self._alerts.fail_open(tenant_id, op)
        except Exception:
            logger.warning("abuse_control.alert_failed", exc_info=True)
