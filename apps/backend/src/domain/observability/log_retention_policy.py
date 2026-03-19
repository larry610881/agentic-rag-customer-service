"""Log Retention Policy — Domain Entity + Repository Interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


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
