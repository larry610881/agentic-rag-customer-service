"""設定變更通知派發（Issue #77）

訂閱 ``AuditRecorder`` 成功寫入的稽核列：bot / worker / 租戶防護設定的變更欄位
對應到欄位群組，與租戶勾選的群組有交集才通知；送到勾選「設定變更」的通知渠道。
系統管理員對租戶的變更（source=platform 或操作者為 system_admin）也通知該租戶，
操作者標「平台」。整個流程 fail-open：任何失敗只記 log。
"""

from __future__ import annotations

from typing import Any

import structlog

from src.domain.audit.entity import AuditEntry
from src.domain.auth.repository import UserRepository
from src.domain.auth.value_objects import Role
from src.domain.bot.repository import BotRepository
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.domain.observability.config_change import (
    GUARD_SETTINGS_ENTITY,
    LONG_TEXT_FIELDS,
    field_label,
    group_label,
    groups_to_notify,
)
from src.domain.observability.notification import NotificationChannelRepository
from src.domain.tenant.repository import TenantRepository

from .notification_use_cases import NotificationDispatcher

_logger = structlog.get_logger(__name__)

SOURCE_PLATFORM = "platform"
PLATFORM_ACTOR_LABEL = "平台"

ENTITY_LABELS = {
    "bot": "機器人",
    "worker": "worker",
    GUARD_SETTINGS_ENTITY: "租戶防護設定",
}
ACTION_LABELS = {"create": "已建立", "update": "已更新", "delete": "已刪除"}

MAX_VALUE_CHARS = 60
MAX_CHANGE_LINES = 12


def _short(value: Any) -> str:
    """通知內容的短格式：None → 「（空）」、list → 逗號、dict → key=value；截長。"""
    if value is None or value == "" or value == []:
        return "（空）"
    if isinstance(value, list):
        text = "、".join(str(v) for v in value)
    elif isinstance(value, dict):
        text = "、".join(f"{k}={v}" for k, v in sorted(value.items()))
    else:
        text = str(value)
    if len(text) > MAX_VALUE_CHARS:
        return text[: MAX_VALUE_CHARS - 1] + "…"
    return text


def _text_len(value: Any) -> int:
    return len(value) if isinstance(value, str) else 0


def format_change_line(field: str, before: Any, after: Any) -> str:
    """單一欄位的變更行；長文字只顯示字數（通知不外洩提示詞全文）。"""
    label = field_label(field)
    if field in LONG_TEXT_FIELDS:
        return f"{label}：{_text_len(before)} 字 → {_text_len(after)} 字"
    return f"{label}：{_short(before)} → {_short(after)}"


class DispatchConfigChangeNotificationUseCase:
    def __init__(
        self,
        channel_repo: NotificationChannelRepository,
        tenant_repository: TenantRepository,
        dispatcher: NotificationDispatcher,
        user_repository: UserRepository | None = None,
        bot_repository: BotRepository | None = None,
        worker_repository: WorkerConfigRepository | None = None,
    ) -> None:
        self._channel_repo = channel_repo
        self._tenant_repo = tenant_repository
        self._dispatcher = dispatcher
        self._user_repo = user_repository
        self._bot_repo = bot_repository
        self._worker_repo = worker_repository

    async def execute(self, entry: AuditEntry) -> int:
        """回傳實際送出的渠道數；任何例外吞掉回 0。"""
        try:
            return await self._execute(entry)
        except Exception:
            _logger.warning(
                "notification.config_change_dispatch_failed",
                entity_type=entry.entity_type, entity_id=entry.entity_id,
                exc_info=True,
            )
            return 0

    async def _execute(self, entry: AuditEntry) -> int:
        if not entry.tenant_id or not entry.changed_fields:
            return 0
        tenant = await self._tenant_repo.find_by_id(entry.tenant_id)
        if tenant is None:
            return 0
        groups = groups_to_notify(
            entity_type=entry.entity_type,
            changed_fields=entry.changed_fields.keys(),
            configured=tenant.config_change_notify_fields,
        )
        if not groups:
            return 0
        channels = [
            ch for ch in await self._channel_repo.list_enabled()
            if ch.notify_config_change
        ]
        if not channels:
            return 0
        subject, body = await self._build_message(entry, tenant.name, groups)
        sent = 0
        for ch in channels:
            await self._dispatcher.send_to_channel(ch, subject, body)
            sent += 1
        return sent

    # ── message ──

    async def _build_message(
        self, entry: AuditEntry, tenant_name: str, groups: list[str]
    ) -> tuple[str, str]:
        entity_label = ENTITY_LABELS.get(entry.entity_type, entry.entity_type)
        entity_name = await self._resolve_entity_name(entry)
        target = (
            f"{entity_label}「{entity_name}」" if entity_name else entity_label
        )
        action = ACTION_LABELS.get(entry.action, entry.action)
        subject = f"[設定變更] {tenant_name}：{target}{action}"

        lines = [
            f"租戶：{tenant_name}",
            f"對象：{target}",
            f"操作者：{await self._resolve_actor(entry)}",
            f"變更群組：{'、'.join(group_label(g) for g in groups)}",
            f"時間：{entry.created_at.isoformat(timespec='seconds')}",
            "",
        ]
        change_lines = [
            format_change_line(name, raw.get("before"), raw.get("after"))
            for name, raw in sorted(entry.changed_fields.items())
            if isinstance(raw, dict)
        ]
        lines += change_lines[:MAX_CHANGE_LINES]
        if len(change_lines) > MAX_CHANGE_LINES:
            lines.append(f"…另有 {len(change_lines) - MAX_CHANGE_LINES} 個欄位變更")
        return subject, "\n".join(lines)

    async def _resolve_actor(self, entry: AuditEntry) -> str:
        if entry.source == SOURCE_PLATFORM:
            return PLATFORM_ACTOR_LABEL
        if not entry.actor_user_id or self._user_repo is None:
            return PLATFORM_ACTOR_LABEL if not entry.actor_user_id else "未知使用者"
        user = await self._user_repo.find_by_id(entry.actor_user_id)
        if user is None:
            return "未知使用者"
        if user.role == Role.SYSTEM_ADMIN or user.tenant_id != entry.tenant_id:
            return PLATFORM_ACTOR_LABEL
        return user.email.value

    async def _resolve_entity_name(self, entry: AuditEntry) -> str | None:
        """bot / worker 名稱：先查目前實體（best-effort），查無再取稽核快照 name。"""
        name: str | None = None
        if entry.entity_type == "bot" and self._bot_repo is not None:
            bot = await self._bot_repo.find_by_id(entry.entity_id)
            name = bot.name if bot is not None else None
        elif entry.entity_type == "worker" and self._worker_repo is not None:
            worker = await self._worker_repo.find_by_id(entry.entity_id)
            name = worker.name if worker is not None else None
        if name:
            return name
        raw = (entry.changed_fields or {}).get("name")
        if isinstance(raw, dict):
            return raw.get("after") or raw.get("before")
        return None
