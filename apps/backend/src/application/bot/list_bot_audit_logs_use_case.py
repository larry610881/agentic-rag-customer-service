"""租戶端 Bot 變更紀錄（Issue #71）

system_admin 的 /audit-logs 存整列 before/after，tenant_admin 沒有入口，導致
「模型被改了不知道誰改」。此 use case 以 bot 為範圍回稽核紀錄：
- 歸屬檢查與 GetBot 一致（跨租戶視同不存在 → 404，不洩漏存在性）
- changed_fields 轉成扁平的 changes 清單；llm_params 展平一層為 `llm_params.<子欄位>`
- 長文字欄位（提示詞類）只回字數，不回全文（全文走 system_admin 稽核頁）
- actor_email 由 user repository 補齊（查無使用者 → None）
- Issue #75：併入平台對該租戶的防護階段變更（entity_type=guard_settings、
  entity_id=tenant:<tenant_id>）；source=platform 的列 actor_label 標「平台」，
  讓租戶看得到「是平台改了我的防護」
- Issue #77：併入該 bot 底下 worker 的稽核列（parent_entity=("bot", bot_id)，
  與 bot 列同一 keyset 查詢聯集）；worker 列附 entity_name（worker 名稱：先查
  目前的 worker，已刪除則取稽核快照中的 name），worker_prompt 同樣只回字數
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.application.bot._tenant_guard import ensure_bot_tenant
from src.domain.audit.entity import (
    AuditEntry,
    AuditLogRepository,
    encode_audit_cursor,
)
from src.domain.auth.repository import UserRepository
from src.domain.bot.repository import BotRepository
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.domain.shared.exceptions import EntityNotFoundError

BOT_ENTITY_TYPE = "bot"
WORKER_ENTITY_TYPE = "worker"          # Issue #77：bot 底下的 worker
GUARD_ENTITY_TYPE = "guard_settings"   # Issue #75：租戶 scope 的防護階段變更
SOURCE_PLATFORM = "platform"
PLATFORM_ACTOR_LABEL = "平台"

# 只回字數的長文字欄位（與 config_snapshot.PROMPT_FIELDS 的提示詞類一致）
LONG_TEXT_FIELDS = frozenset({
    "bot_prompt",
    "base_prompt",
    "memory_extraction_prompt",
    "worker_prompt",  # Issue #77：worker 列
})

# 展平一層的巢狀欄位
NESTED_FIELDS = frozenset({"llm_params"})

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class BotAuditChange:
    field: str
    before: Any = None
    after: Any = None
    before_len: int | None = None
    after_len: int | None = None
    # 長文字欄位：只標記有變更 + 字數，不附全文
    changed: bool = True

    @property
    def is_long_text(self) -> bool:
        return self.before_len is not None or self.after_len is not None


@dataclass(frozen=True)
class BotAuditLogEntry:
    id: str
    action: str
    actor_user_id: str | None
    actor_email: str | None
    created_at: datetime
    source: str
    changes: list[BotAuditChange] = field(default_factory=list)
    entity_type: str = BOT_ENTITY_TYPE
    # Issue #75：平台（system_admin）對此租戶的變更 → "平台"；其餘 None（顯示 email）
    actor_label: str | None = None
    # Issue #77：worker 列的 entity_id / 名稱（UI 顯示「worker：門市」）；bot 列為 None
    entity_id: str | None = None
    entity_name: str | None = None


@dataclass(frozen=True)
class BotAuditLogPage:
    items: list[BotAuditLogEntry]
    next_cursor: str | None = None


def _text_len(value: Any) -> int:
    return len(value) if isinstance(value, str) else 0


def _long_text_change(name: str, before: Any, after: Any) -> BotAuditChange:
    return BotAuditChange(
        field=name,
        before_len=_text_len(before),
        after_len=_text_len(after),
        changed=True,
    )


def _snapshot_name(entry: AuditEntry) -> str | None:
    """已刪除的 worker：取稽核列快照中的 name（delete 列 before、create 列 after）。"""
    raw = (entry.changed_fields or {}).get("name")
    if not isinstance(raw, dict):
        return None
    name = raw.get("after") or raw.get("before")
    return name if isinstance(name, str) and name else None


def build_changes(changed_fields: dict[str, Any] | None) -> list[BotAuditChange]:
    """稽核列的 changed_fields（{field: {before, after}}）→ 扁平 changes 清單。"""
    changes: list[BotAuditChange] = []
    for name in sorted(changed_fields or {}):
        raw = (changed_fields or {})[name]
        if not isinstance(raw, dict):
            continue
        before, after = raw.get("before"), raw.get("after")
        if name in NESTED_FIELDS:
            b_map = before if isinstance(before, dict) else {}
            a_map = after if isinstance(after, dict) else {}
            for sub in sorted(set(b_map) | set(a_map)):
                if b_map.get(sub) != a_map.get(sub):
                    changes.append(BotAuditChange(
                        field=f"{name}.{sub}",
                        before=b_map.get(sub),
                        after=a_map.get(sub),
                    ))
            continue
        if name in LONG_TEXT_FIELDS:
            changes.append(_long_text_change(name, before, after))
            continue
        changes.append(BotAuditChange(field=name, before=before, after=after))
    return changes


class ListBotAuditLogsUseCase:
    def __init__(
        self,
        bot_repository: BotRepository,
        audit_log_repository: AuditLogRepository,
        user_repository: UserRepository | None = None,
        worker_repository: WorkerConfigRepository | None = None,
    ) -> None:
        self._bot_repo = bot_repository
        self._audit_repo = audit_log_repository
        self._user_repo = user_repository
        self._worker_repo = worker_repository

    async def execute(
        self,
        bot_id: str,
        *,
        tenant_id: str,
        role: str | None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> BotAuditLogPage:
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", bot_id)
        ensure_bot_tenant(bot, tenant_id, role)

        limit = max(1, min(limit, MAX_LIMIT))
        # Issue #75：平台對此租戶的防護階段變更（同一 keyset cursor 套在兩個來源上，
        # 各取 limit+1 再合併排序，next_cursor 仍指向本頁最後一筆）
        guard_entries = await self._find_entries(
            GUARD_ENTITY_TYPE, f"tenant:{bot.tenant_id}", limit, cursor
        )
        # Issue #77：bot 列 ∪ 其 worker 列（parent=bot）單一 keyset 查詢；
        # 多取一筆判斷下一頁
        bot_entries = await self._audit_repo.find_by_entity_or_parent(
            entity_type=BOT_ENTITY_TYPE,
            entity_id=bot.id.value,
            parent_entity_type=BOT_ENTITY_TYPE,
            parent_entity_id=bot.id.value,
            limit=limit + 1,
            cursor=cursor,
        )
        entries = sorted(
            [*bot_entries, *guard_entries],
            key=lambda e: (e.created_at, e.id),
            reverse=True,
        )
        has_more = len(entries) > limit
        page_entries = entries[:limit]
        emails = await self._resolve_actor_emails(page_entries)
        worker_names = await self._resolve_worker_names(bot.id.value, page_entries)
        items = [
            BotAuditLogEntry(
                id=e.id,
                action=e.action,
                actor_user_id=e.actor_user_id,
                actor_email=emails.get(e.actor_user_id or ""),
                created_at=e.created_at,
                source=e.source,
                changes=build_changes(e.changed_fields),
                entity_type=e.entity_type,
                actor_label=(
                    PLATFORM_ACTOR_LABEL if e.source == SOURCE_PLATFORM else None
                ),
                entity_id=(
                    e.entity_id if e.entity_type == WORKER_ENTITY_TYPE else None
                ),
                entity_name=(
                    worker_names.get(e.entity_id) or _snapshot_name(e)
                    if e.entity_type == WORKER_ENTITY_TYPE else None
                ),
            )
            for e in page_entries
        ]
        next_cursor = (
            encode_audit_cursor(page_entries[-1]) if has_more and page_entries else None
        )
        return BotAuditLogPage(items=items, next_cursor=next_cursor)

    async def _find_entries(
        self, entity_type: str, entity_id: str, limit: int, cursor: str | None
    ) -> list[AuditEntry]:
        """單一實體的稽核列（多取一筆判斷下一頁）；只留符合 entity_type 的列。"""
        entries = await self._audit_repo.find_by_entity(
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit + 1,
            cursor=cursor,
        )
        return [e for e in entries if e.entity_type == entity_type]

    async def _resolve_worker_names(
        self, bot_id: str, entries: list[AuditEntry]
    ) -> dict[str, str]:
        """Issue #77：本頁有 worker 列才查一次 bot 的 worker 清單（id → 名稱）。"""
        if self._worker_repo is None or not any(
            e.entity_type == WORKER_ENTITY_TYPE for e in entries
        ):
            return {}
        workers = await self._worker_repo.find_by_bot_id(bot_id)
        return {w.id: w.name for w in workers if w.name}

    async def _resolve_actor_emails(
        self, entries: list[AuditEntry]
    ) -> dict[str, str]:
        """同一頁的 actor 通常只有一兩位，逐一查即可（查無 → 略過）。"""
        if self._user_repo is None:
            return {}
        emails: dict[str, str] = {}
        for actor_id in {e.actor_user_id for e in entries if e.actor_user_id}:
            user = await self._user_repo.find_by_id(actor_id)
            if user is not None:
                emails[actor_id] = user.email.value
        return emails
