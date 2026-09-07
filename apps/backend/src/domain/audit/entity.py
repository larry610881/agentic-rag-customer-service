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
    # Issue #77：所屬上層實體（worker → ("bot", bot_id)），讓租戶端 bot 變更紀錄併入
    parent_entity_type: str | None = None
    parent_entity_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


_CURSOR_SEP = "|"


def encode_audit_cursor(entry: AuditEntry) -> str:
    """Issue #71：keyset 分頁游標 = `<created_at ISO>|<id>`（時間相同時以 id 決勝）。"""
    return f"{entry.created_at.isoformat()}{_CURSOR_SEP}{entry.id}"


def decode_audit_cursor(cursor: str) -> tuple[datetime, str]:
    """解析游標；格式錯誤 raise ValueError（interfaces 層轉 422）。"""
    ts_text, sep, entry_id = cursor.partition(_CURSOR_SEP)
    if not sep or not entry_id:
        raise ValueError("invalid audit cursor")
    ts = datetime.fromisoformat(ts_text)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts, entry_id


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

    @abstractmethod
    async def find_by_entity(
        self,
        *,
        entity_type: str,
        entity_id: str,
        limit: int,
        cursor: str | None = None,
    ) -> list[AuditEntry]:
        """Issue #71：單一實體的稽核紀錄，新→舊，keyset 分頁。
        cursor 為 ``encode_audit_cursor`` 產物；帶入時只回比它更舊的列。"""
        ...

    @abstractmethod
    async def find_by_entity_or_parent(
        self,
        *,
        entity_type: str,
        entity_id: str,
        parent_entity_type: str,
        parent_entity_id: str,
        limit: int,
        cursor: str | None = None,
    ) -> list[AuditEntry]:
        """Issue #77：實體本身的列 ∪ 以它為 parent 的列（bot ∪ 其 worker），
        單一 keyset 查詢，新→舊（created_at desc, id desc）。"""
        ...
