"""管理端變更稽核（Issue #60）

指紋回答「那一輪跑了什麼」；稽核回答「是誰、何時、透過什麼路徑改成這樣」。
只存變更欄位的 before/after，不存整列。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

SOURCE_API = "api"
SOURCE_OPTIMIZER = "optimizer"
SOURCE_ROLLBACK = "rollback"
SOURCE_MIGRATION = "migration"


@dataclass
class AuditEntry:
    entity_type: str
    entity_id: str
    action: str  # create | update | delete | reset
    changed_fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    actor_user_id: str | None = None
    tenant_id: str | None = None
    source: str = SOURCE_API
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AuditLogRepository(ABC):
    @abstractmethod
    async def append(self, entry: AuditEntry) -> None: ...

    @abstractmethod
    async def list_entries(
        self,
        *,
        tenant_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEntry]: ...
