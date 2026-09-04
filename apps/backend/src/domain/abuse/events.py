"""異常控管告警事件（Issue #68 P7c）

通知內容不含使用者原文與完整 id：主體 id 一律遮罩，只帶種類、通路、等級、原因摘要、
剩餘時間與後台連結。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class AbuseAlertKind(StrEnum):
    ESCALATION = "escalation"  # 主體升到 L3 / L4
    FAIL_OPEN = "fail_open"    # 分數儲存不可用而放行——控管默默失效的唯一線索
    SURGE = "surge"            # 429 / L2 觸發突增（每租戶 5 分鐘視窗）
    REPORT = "report"          # 例行摘要（每日）


def mask_subject_id(subject_id: str) -> str:
    """`abcdef-1234` → `abcd…34`；短 id 只留前 2 碼。"""
    if not subject_id:
        return "-"
    if len(subject_id) <= 6:
        return subject_id[:2] + "…"
    return f"{subject_id[:4]}…{subject_id[-2:]}"


@dataclass(frozen=True)
class AbuseAlertEvent:
    kind: AbuseAlertKind
    tenant_id: str
    fingerprint: str
    level: int = 0
    subject_kind: str = ""
    subject_masked: str = ""
    channel: str = ""
    reasons: tuple[str, ...] = ()
    retry_after: int = 0
    summary_lines: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def title(self) -> str:
        if self.kind is AbuseAlertKind.ESCALATION:
            state = "封鎖" if self.level >= 4 else "冷卻"
            return f"[Abuse L{self.level}] 主體進入{state}"
        if self.kind is AbuseAlertKind.FAIL_OPEN:
            return "[Abuse] 控管儲存不可用，已放行（fail-open）"
        if self.kind is AbuseAlertKind.SURGE:
            return "[Abuse] 429 / 降速觸發突增"
        return "[Abuse] 每日異常控管摘要"
