"""異常控管告警（Issue #68 P7c）

- L3 / L4 升級 → 立即告警
- fail-open（分數儲存不可用）→ 告警 + 計數（每租戶冷卻 15 分鐘）
- 429 / L2 突增 → 每租戶 5 分鐘視窗超過門檻發一次
發送交給 publisher（fire-and-forget 到 notification channels）；本身永不拋例外。
"""

import hashlib
from collections.abc import Awaitable, Callable

import structlog

from src.domain.abuse.events import AbuseAlertEvent, AbuseAlertKind, mask_subject_id
from src.domain.abuse.policy import AbuseLevel, AbuseSubject
from src.domain.abuse.store import AbuseScoreStore

logger = structlog.get_logger(__name__)

AbuseAlertPublisher = Callable[[AbuseAlertEvent], Awaitable[None]]

FAIL_OPEN_COUNTER_TTL = 86400


class AbuseAlertService:
    def __init__(
        self,
        store: AbuseScoreStore,
        publish: AbuseAlertPublisher,
        *,
        surge_threshold: int = 20,
        surge_window_seconds: int = 300,
        fail_open_cooldown_seconds: int = 900,
        admin_link: str = "/admin/audit-logs?entity_type=abuse_control",
    ) -> None:
        self._store = store
        self._publish = publish
        self._surge_threshold = surge_threshold
        self._surge_window = surge_window_seconds
        self._fail_open_cooldown = fail_open_cooldown_seconds
        self._admin_link = admin_link

    async def escalated(
        self,
        tenant_id: str,
        subject: AbuseSubject,
        level: AbuseLevel,
        *,
        reasons: tuple[str, ...],
        retry_after: int,
        channel: str,
    ) -> None:
        if level == AbuseLevel.SLOW:
            await self._bump_surge(tenant_id, "slowdown")
            return
        if level < AbuseLevel.COOLDOWN:
            return
        await self._safe_publish(AbuseAlertEvent(
            kind=AbuseAlertKind.ESCALATION,
            tenant_id=tenant_id,
            # 節流指紋也不帶完整 id（log 亦不外洩）
            fingerprint=(
                f"abuse:escalation:{tenant_id}:"
                f"{hashlib.sha256(subject.key(tenant_id).encode()).hexdigest()[:12]}"
                f":{int(level)}"
            ),
            level=int(level),
            subject_kind=subject.kind.value,
            subject_masked=mask_subject_id(subject.id),
            channel=channel,
            reasons=reasons,
            retry_after=retry_after,
            summary_lines=(f"後台：{self._admin_link}",),
        ))

    async def rate_limited(self, tenant_id: str | None) -> None:
        if tenant_id:
            await self._bump_surge(tenant_id, "429")

    async def fail_open(self, tenant_id: str, op: str) -> None:
        """儲存不可用：計數 + 告警（同租戶 15 分鐘內只發一次）。計數失敗也照發。"""
        count = None
        should_publish = True
        try:
            count = await self._store.incr_counter(
                f"abuse:failopen:{tenant_id}", FAIL_OPEN_COUNTER_TTL
            )
            should_publish = (
                await self._store.incr_counter(
                    f"abuse:failopen_alert:{tenant_id}", self._fail_open_cooldown
                ) == 1
            )
        except Exception:
            pass  # 儲存本來就掛了；照發告警，靠 notification 層節流
        if not should_publish:
            return
        await self._safe_publish(AbuseAlertEvent(
            kind=AbuseAlertKind.FAIL_OPEN,
            tenant_id=tenant_id,
            fingerprint=f"abuse:fail_open:{tenant_id}",
            summary_lines=(
                f"操作：{op}",
                f"今日累計：{count if count is not None else '未知（儲存不可用）'}",
                f"後台：{self._admin_link}",
            ),
        ))

    async def _bump_surge(self, tenant_id: str, source: str) -> None:
        try:
            count = await self._store.incr_counter(
                f"abuse:surge:{tenant_id}", self._surge_window
            )
        except Exception:
            return
        if count != self._surge_threshold:
            return  # 視窗內只在剛越過門檻時發一次
        await self._safe_publish(AbuseAlertEvent(
            kind=AbuseAlertKind.SURGE,
            tenant_id=tenant_id,
            fingerprint=f"abuse:surge:{tenant_id}",
            summary_lines=(
                f"{self._surge_window // 60} 分鐘內 429 / 降速觸發 {count} 次"
                f"（最新來源：{source}）",
                f"後台：{self._admin_link}",
            ),
        ))

    async def _safe_publish(self, event: AbuseAlertEvent) -> None:
        try:
            await self._publish(event)
        except Exception:
            logger.warning("abuse_alert.publish_failed", kind=event.kind.value)
