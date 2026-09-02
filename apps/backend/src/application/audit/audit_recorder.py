"""稽核紀錄器（Issue #60）

管理端 use case 在寫入前後各取一份「可稽核視圖」dict，呼叫 ``record``：只有
差異欄位進 changed_fields（長字串截斷），無差異不寫。repository 失敗 fail-open
（稽核不能反過來擋掉管理操作，但要留 warning log）。
"""

from __future__ import annotations

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


class AuditRecorder:
    def __init__(
        self,
        repository: AuditLogRepository | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self._repo = repository
        self._session_factory = session_factory

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
