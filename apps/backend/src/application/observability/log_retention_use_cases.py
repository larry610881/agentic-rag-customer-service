"""Log Retention Policy CRUD + Execute Use Cases."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.domain.observability.log_retention_policy import (
    LogRetentionPolicy,
    LogRetentionPolicyRepository,
)


class GetLogRetentionPolicyUseCase:
    def __init__(
        self,
        log_retention_policy_repository: LogRetentionPolicyRepository,
    ) -> None:
        self._repo = log_retention_policy_repository

    async def execute(self) -> LogRetentionPolicy:
        policy = await self._repo.get()
        if policy is not None:
            return policy
        return LogRetentionPolicy()


@dataclass(frozen=True)
class UpdateLogRetentionPolicyCommand:
    enabled: bool
    retention_days: int
    cleanup_hour: int
    cleanup_interval_hours: int


class UpdateLogRetentionPolicyUseCase:
    def __init__(
        self,
        log_retention_policy_repository: LogRetentionPolicyRepository,
    ) -> None:
        self._repo = log_retention_policy_repository

    async def execute(
        self, command: UpdateLogRetentionPolicyCommand
    ) -> LogRetentionPolicy:
        existing = await self._repo.get()
        policy = LogRetentionPolicy(
            enabled=command.enabled,
            retention_days=command.retention_days,
            cleanup_hour=command.cleanup_hour,
            cleanup_interval_hours=command.cleanup_interval_hours,
            last_cleanup_at=existing.last_cleanup_at if existing else None,
            deleted_count_last=existing.deleted_count_last if existing else 0,
        )
        return await self._repo.save(policy)


class ExecuteLogCleanupUseCase:
    """Immediately execute log cleanup based on retention_days."""

    def __init__(
        self,
        log_retention_policy_repository: LogRetentionPolicyRepository,
    ) -> None:
        self._repo = log_retention_policy_repository

    async def execute(self, retention_days: int | None = None) -> int:
        policy = await self._repo.get()
        days = retention_days or (policy.retention_days if policy else 30)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = await self._repo.cleanup_logs_before(cutoff)

        if policy is None:
            policy = LogRetentionPolicy()
        policy.last_cleanup_at = datetime.now(timezone.utc)
        policy.deleted_count_last = count
        await self._repo.save(policy)

        return count
