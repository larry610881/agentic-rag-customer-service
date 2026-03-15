"""Error Event — Domain Entity + Repository Interface."""

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Normalize UUIDs and numeric IDs in paths
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)
_HEX_ID_RE = re.compile(r"/[0-9a-f]{12,}/")
_NUMERIC_ID_RE = re.compile(r"/\d+(/|$)")


def normalize_path(path: str) -> str:
    """Replace UUIDs, hex IDs, and numeric IDs with :id placeholder."""
    result = _UUID_RE.sub(":id", path)
    result = _HEX_ID_RE.sub("/:id/", result)
    result = _NUMERIC_ID_RE.sub("/:id\\1", result)
    return result


def compute_fingerprint(source: str, error_type: str, path: str | None) -> str:
    """SHA-256 based fingerprint for error grouping."""
    normalized = normalize_path(path or "")
    raw = f"{source}|{error_type}|{normalized}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ErrorEvent:
    id: str
    fingerprint: str
    source: str  # 'backend' | 'frontend' | 'widget'
    error_type: str
    message: str
    stack_trace: str | None = None
    request_id: str | None = None
    path: str | None = None
    method: str | None = None
    status_code: int | None = None
    tenant_id: str | None = None
    user_agent: str | None = None
    extra: dict | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorEventRepository(ABC):
    @abstractmethod
    async def save(self, event: ErrorEvent) -> ErrorEvent: ...

    @abstractmethod
    async def get_by_id(self, event_id: str) -> ErrorEvent | None: ...

    @abstractmethod
    async def list_events(
        self,
        *,
        source: str | None = None,
        resolved: bool | None = None,
        fingerprint: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ErrorEvent], int]: ...

    @abstractmethod
    async def resolve(
        self, event_id: str, resolved_by: str
    ) -> ErrorEvent | None: ...

    @abstractmethod
    async def count_by_fingerprint(self, fingerprint: str) -> int: ...

    @abstractmethod
    async def last_notified_at(
        self, fingerprint: str, channel_id: str
    ) -> datetime | None: ...

    @abstractmethod
    async def record_notification(
        self, fingerprint: str, channel_id: str
    ) -> None: ...

    @abstractmethod
    async def cleanup_before(self, cutoff: datetime) -> int: ...
