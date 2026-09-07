"""稽核紀錄器（Issue #60）

管理端 use case 在寫入前後各取一份「可稽核視圖」dict，呼叫 ``record``：只有
差異欄位進 changed_fields（長字串截斷），無差異不寫。repository 失敗 fail-open
（稽核不能反過來擋掉管理操作，但要留 warning log）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from src.domain.audit.entity import SOURCE_API, AuditEntry, AuditLogRepository

logger = structlog.get_logger(__name__)

MAX_VALUE_CHARS = 2000


_TRUNCATED_MARK = "…[truncated]"


def _clip(value: Any) -> Any:
    """長字串截到 MAX_VALUE_CHARS（含標記），避免 prompt 全文塞爆稽核列。"""
    if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
        return value[: MAX_VALUE_CHARS - len(_TRUNCATED_MARK)] + _TRUNCATED_MARK
    return value


def diff_views(before: dict | None, after: dict | None) -> dict[str, dict[str, Any]]:
    before = before or {}
    after = after or {}
    changed: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key), after.get(key)
        if b != a:
            changed[key] = {"before": _clip(b), "after": _clip(a)}
    return changed


AuditHook = Callable[[AuditEntry], Awaitable[None]]


class AuditRecorder:
    """``on_recorded``（Issue #77）：稽核列成功寫入後的掛勾（設定變更通知）。
    掛勾失敗只記 warning，絕不讓管理操作失敗。"""

    def __init__(
        self,
        repository: AuditLogRepository | None = None,
        session_factory: Any | None = None,
        on_recorded: AuditHook | None = None,
    ) -> None:
        self._repo = repository
        self._session_factory = session_factory
        self._on_recorded = on_recorded

    async def _append(self, entry: AuditEntry) -> None:
        if self._repo is not None:
            await self._repo.append(entry)
            return
        if self._session_factory is None:
            return
        from src.infrastructure.db.repositories.audit_log_repository import (
            SQLAlchemyAuditLogRepository,
        )

        async with self._session_factory() as session:
            await SQLAlchemyAuditLogRepository(session).append(entry)

    async def record(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        before: dict | None,
        after: dict | None,
        actor_user_id: str | None,
        tenant_id: str | None = None,
        source: str = SOURCE_API,
        parent_entity_type: str | None = None,
        parent_entity_id: str | None = None,
    ) -> AuditEntry | None:
        changed = diff_views(before, after)
        if not changed and action == "update":
            return None
        entry = AuditEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changed_fields=changed,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
            source=source,
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
        )
        try:
            await self._append(entry)
        except Exception:
            logger.warning(
                "audit.append_failed",
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                exc_info=True,
            )
            return entry
        await self._notify(entry)
        return entry

    async def _notify(self, entry: AuditEntry) -> None:
        if self._on_recorded is None:
            return
        try:
            await self._on_recorded(entry)
        except Exception:
            logger.warning(
                "audit.on_recorded_failed",
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                exc_info=True,
            )


class ListAuditLogsUseCase:
    def __init__(self, repository: AuditLogRepository) -> None:
        self._repo = repository

    async def execute(
        self,
        *,
        tenant_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEntry]:
        return await self._repo.list_entries(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
