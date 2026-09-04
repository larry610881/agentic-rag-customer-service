"""每日異常控管摘要（Issue #68 P7c）— 從稽核紀錄彙整，走同一批通知渠道。"""

from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from src.domain.abuse.events import AbuseAlertEvent, AbuseAlertKind, mask_subject_id
from src.domain.abuse.store import AbuseScoreStore
from src.domain.audit.entity import AuditEntry, AuditLogRepository

AUDIT_ENTITY = "abuse_control"


def _after_level(entry: AuditEntry) -> int | None:
    field = entry.changed_fields.get("level") or {}
    value = field.get("after") if isinstance(field, dict) else None
    return int(value) if isinstance(value, int) else None


def _subject_from_key(entity_id: str) -> tuple[str, str]:
    # abuse:{tenant}:{kind}:{id}
    parts = entity_id.split(":", 3)
    if len(parts) == 4:
        return parts[2], parts[3]
    return "?", entity_id


def summarize_entries(
    entries: list[AuditEntry], *, since: datetime, fail_open_count: int | None = None
) -> tuple[str, ...]:
    """把一段時間的稽核紀錄彙整成摘要行（可單獨測試）。"""
    recent = [e for e in entries if e.created_at >= since]
    by_level: Counter[int] = Counter()
    releases = 0
    subjects: Counter[str] = Counter()
    for e in recent:
        if e.action == "escalate":
            level = _after_level(e)
            if level is not None:
                by_level[level] += 1
            kind, sid = _subject_from_key(e.entity_id)
            subjects[f"{kind} {mask_subject_id(sid)}"] += 1
        elif e.action == "release":
            releases += 1
    lines = [
        "升級次數："
        f"L1 {by_level[1]}、L2 {by_level[2]}、L3 {by_level[3]}、L4 {by_level[4]}",
        f"手動解除：{releases}",
    ]
    if fail_open_count is not None:
        lines.append(f"fail-open 次數：{fail_open_count}")
    top = subjects.most_common(5)
    if top:
        lines.append("Top 主體：" + "、".join(f"{s}（{n}）" for s, n in top))
    else:
        lines.append("Top 主體：無")
    return tuple(lines)


class BuildAbuseReportUseCase:
    def __init__(
        self,
        audit_repo: AuditLogRepository,
        store: AbuseScoreStore,
        publish: Callable[[AbuseAlertEvent], Awaitable[None]],
        *,
        window_hours: int = 24,
    ) -> None:
        self._audit = audit_repo
        self._store = store
        self._publish = publish
        self._window = timedelta(hours=window_hours)

    async def execute(self, now: datetime | None = None) -> int:
        """回傳送出的租戶摘要數。"""
        now = now or datetime.now(timezone.utc)
        since = now - self._window
        entries = await self._audit.list_entries(entity_type=AUDIT_ENTITY, limit=2000)
        tenants = sorted({
            e.tenant_id for e in entries if e.tenant_id and e.created_at >= since
        })
        sent = 0
        for tenant_id in tenants:
            fail_open = None
            try:
                fail_open = await self._store.incr_counter(
                    f"abuse:failopen:{tenant_id}", 86400
                ) - 1  # incr 後 -1 = 讀值（store 只有 incr 介面）
            except Exception:
                fail_open = None
            lines = summarize_entries(
                [e for e in entries if e.tenant_id == tenant_id],
                since=since, fail_open_count=fail_open,
            )
            await self._publish(AbuseAlertEvent(
                kind=AbuseAlertKind.REPORT,
                tenant_id=tenant_id,
                fingerprint=f"abuse:report:{tenant_id}:{now:%Y%m%d}",
                summary_lines=lines,
                created_at=now,
            ))
            sent += 1
        return sent
