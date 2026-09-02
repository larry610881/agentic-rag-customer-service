"""Log Retention Policy — Domain Entity + Repository Interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class LogRetentionPolicy:
    """全域日誌清理策略（singleton, id='system'）"""

    id: str = "system"
    enabled: bool = True
    retention_days: int = 30
    cleanup_hour: int = 3  # 0-23
    cleanup_interval_hours: int = 24  # 24=每天一次, 12=每天兩次
    last_cleanup_at: datetime | None = None
    deleted_count_last: int = 0
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class LogRetentionPolicyRepository(ABC):
    @abstractmethod
    async def get(self) -> LogRetentionPolicy | None: ...

    @abstractmethod
    async def save(self, policy: LogRetentionPolicy) -> LogRetentionPolicy: ...

    @abstractmethod
    async def cleanup_logs_before(self, cutoff: datetime) -> int:
        """Delete request_logs older than cutoff. Returns deleted count."""
        ...


def should_run_cleanup(policy: LogRetentionPolicy, now: datetime) -> bool:
    """Issue #59：worker 每小時呼叫，判斷此刻是否該執行清理。

    - 未啟用 → 否
    - 只在 cleanup_hour 起算、每 cleanup_interval_hours 的整點執行
    - 同一小時內已執行過（last_cleanup_at 距今 < 1 小時）→ 否，避免重複
    """
    if not policy.enabled:
        return False
    interval = max(1, int(policy.cleanup_interval_hours or 24))
    if (now.hour - policy.cleanup_hour) % interval != 0:
        return False
    last = policy.last_cleanup_at
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=now.tzinfo)
        if now - last < timedelta(hours=1):
            return False
    return True
