"""Notification Channel Use Cases — CRUD, test, dispatch."""

import json
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone

import structlog

from src.domain.abuse.events import AbuseAlertEvent, AbuseAlertKind
from src.domain.observability.diagnostic import DiagnosticEvent
from src.domain.observability.error_event import ErrorEvent
from src.domain.observability.notification import (
    NotificationChannel,
    NotificationChannelRepository,
    NotificationSender,
    NotificationThrottleService,
)
from src.domain.platform.services import EncryptionService
from src.domain.shared.exceptions import EntityNotFoundError

_logger = structlog.get_logger(__name__)


class ListChannelsUseCase:
    def __init__(
        self, channel_repo: NotificationChannelRepository
    ) -> None:
        self._repo = channel_repo

    async def execute(self) -> list[NotificationChannel]:
        return await self._repo.list_all()


@dataclass(frozen=True)
class CreateChannelCommand:
    channel_type: str
    name: str
    enabled: bool = False
    config: dict | None = None
    throttle_minutes: int = 15
    min_severity: str = "all"
    notify_diagnostics: bool = False
    diagnostic_severity: str = "critical"
    notify_abuse: bool = True


class CreateChannelUseCase:
    def __init__(
        self,
        channel_repo: NotificationChannelRepository,
        encryption_service: EncryptionService,
    ) -> None:
        self._repo = channel_repo
        self._enc = encryption_service

    async def execute(self, command: CreateChannelCommand) -> NotificationChannel:
        config_json = json.dumps(command.config or {})
        encrypted = self._enc.encrypt(config_json)
        channel = NotificationChannel(
            id=uuid.uuid4().hex,
            channel_type=command.channel_type,
            name=command.name,
            enabled=command.enabled,
            config_encrypted=encrypted,
            throttle_minutes=command.throttle_minutes,
            min_severity=command.min_severity,
            notify_diagnostics=command.notify_diagnostics,
            diagnostic_severity=command.diagnostic_severity,
            notify_abuse=command.notify_abuse,
        )
        return await self._repo.save(channel)


@dataclass(frozen=True)
class UpdateChannelCommand:
    channel_id: str
    name: str | None = None
    enabled: bool | None = None
    config: dict | None = None
    throttle_minutes: int | None = None
    min_severity: str | None = None
    notify_diagnostics: bool | None = None
    diagnostic_severity: str | None = None
    notify_abuse: bool | None = None


class UpdateChannelUseCase:
    def __init__(
        self,
        channel_repo: NotificationChannelRepository,
        encryption_service: EncryptionService,
    ) -> None:
        self._repo = channel_repo
        self._enc = encryption_service

    async def execute(self, command: UpdateChannelCommand) -> NotificationChannel:
        channel = await self._repo.get_by_id(command.channel_id)
        if channel is None:
            raise EntityNotFoundError("NotificationChannel", command.channel_id)
        if command.name is not None:
            channel.name = command.name
        if command.enabled is not None:
            channel.enabled = command.enabled
        if command.config is not None:
            channel.config_encrypted = self._enc.encrypt(
                json.dumps(command.config)
            )
        if command.throttle_minutes is not None:
            channel.throttle_minutes = command.throttle_minutes
        if command.min_severity is not None:
            channel.min_severity = command.min_severity
        if command.notify_diagnostics is not None:
            channel.notify_diagnostics = command.notify_diagnostics
        if command.diagnostic_severity is not None:
            channel.diagnostic_severity = command.diagnostic_severity
        if command.notify_abuse is not None:
            channel.notify_abuse = command.notify_abuse
        channel.updated_at = datetime.now(timezone.utc)
        return await self._repo.save(channel)


class DeleteChannelUseCase:
    def __init__(
        self, channel_repo: NotificationChannelRepository
    ) -> None:
        self._repo = channel_repo

    async def execute(self, channel_id: str) -> bool:
        return await self._repo.delete(channel_id)


class SendTestNotificationUseCase:
    def __init__(
        self,
        channel_repo: NotificationChannelRepository,
        encryption_service: EncryptionService,
        dispatcher: "NotificationDispatcher",
    ) -> None:
        self._repo = channel_repo
        self._enc = encryption_service
        self._dispatcher = dispatcher

    async def execute(self, channel_id: str) -> None:
        channel = await self._repo.get_by_id(channel_id)
        if channel is None:
            raise EntityNotFoundError("NotificationChannel", channel_id)
        await self._dispatcher.send_to_channel(
            channel,
            subject="[Test] Error Tracking Notification",
            body="This is a test notification from the error tracking system.",
        )


class NotificationDispatcher:
    """Holds sender implementations, dispatches by channel_type.

    Issue #68 P7c：config 在此解密後交給 sender（sender 一律拿到明文 JSON）；
    單一渠道失敗只記 log，不讓整批通知中斷。
    """

    def __init__(
        self,
        senders: dict[str, NotificationSender],
        encryption_service: EncryptionService | None = None,
    ) -> None:
        self._senders = senders
        self._enc = encryption_service

    def _with_plain_config(self, channel: NotificationChannel) -> NotificationChannel:
        if self._enc is None or not channel.config_encrypted:
            return channel
        raw = channel.config_encrypted
        try:
            json.loads(raw)
            return channel  # 已是明文
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            plain = self._enc.decrypt(raw)
        except Exception:
            _logger.warning("notification.config_decrypt_failed", channel_id=channel.id)
            return channel
        return replace(channel, config_encrypted=plain)

    async def send_to_channel(
        self,
        channel: NotificationChannel,
        subject: str,
        body: str,
    ) -> None:
        sender = self._senders.get(channel.channel_type)
        if sender is None:
            _logger.warning(
                "notification.no_sender",
                channel_type=channel.channel_type,
            )
            return
        try:
            await sender.send(self._with_plain_config(channel), subject, body)
        except Exception:
            _logger.warning(
                "notification.send_failed",
                channel_id=channel.id, channel_type=channel.channel_type,
                exc_info=True,
            )


class DispatchNotificationUseCase:
    """Load enabled channels, check throttle, dispatch notifications."""

    def __init__(
        self,
        channel_repo: NotificationChannelRepository,
        throttle_service: NotificationThrottleService,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._channel_repo = channel_repo
        self._throttle = throttle_service
        self._dispatcher = dispatcher

    async def execute(self, event: ErrorEvent) -> None:
        try:
            channels = await self._channel_repo.list_enabled()
            for ch in channels:
                if ch.min_severity == "off":
                    continue
                if await self._throttle.is_throttled(event.fingerprint, ch.id):
                    continue
                subject = f"[Error] {event.error_type}: {event.message[:80]}"
                body = (
                    f"Source: {event.source}\n"
                    f"Path: {event.path}\n"
                    f"Fingerprint: {event.fingerprint}\n"
                    f"Time: {event.created_at.isoformat()}\n"
                    f"Message: {event.message}"
                )
                await self._dispatcher.send_to_channel(ch, subject, body)
                await self._throttle.record_sent(
                    event.fingerprint, ch.id, ch.throttle_minutes * 60
                )
        except Exception:
            _logger.warning("notification.dispatch_failed", exc_info=True)


class DispatchDiagnosticNotificationUseCase:
    """Load enabled channels with notify_diagnostics=True, check throttle, dispatch."""

    # Severity rank: lower = more severe. "all" accepts everything.
    _SEVERITY_RANK = {"critical": 0, "warning": 1}

    def __init__(
        self,
        channel_repo: NotificationChannelRepository,
        throttle_service: NotificationThrottleService,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._channel_repo = channel_repo
        self._throttle = throttle_service
        self._dispatcher = dispatcher

    def _should_notify(self, channel_severity: str, event_severity: str) -> bool:
        """Check if event severity meets channel's threshold.

        channel_severity="critical"  → only critical
        channel_severity="warning"   → warning + critical
        channel_severity="all"       → everything
        """
        if channel_severity == "all":
            return True
        ch_rank = self._SEVERITY_RANK.get(channel_severity)
        ev_rank = self._SEVERITY_RANK.get(event_severity)
        if ch_rank is None or ev_rank is None:
            return False  # unknown severity → skip
        return ev_rank <= ch_rank  # event must be equal or more severe

    async def execute(self, event: DiagnosticEvent) -> None:
        try:
            channels = await self._channel_repo.list_enabled()
            for ch in channels:
                if not ch.notify_diagnostics:
                    continue
                if not self._should_notify(ch.diagnostic_severity, event.severity):
                    continue
                if await self._throttle.is_throttled(event.fingerprint, ch.id):
                    continue
                subject = (
                    f"[RAG {event.severity.upper()}] "
                    f"{event.hints[0].dimension} 品質異常"
                )
                body = self._format_body(event)
                await self._dispatcher.send_to_channel(ch, subject, body)
                await self._throttle.record_sent(
                    event.fingerprint, ch.id, ch.throttle_minutes * 60
                )
        except Exception:
            _logger.warning(
                "notification.diagnostic_dispatch_failed", exc_info=True
            )

    @staticmethod
    def _format_body(event: DiagnosticEvent) -> str:
        lines = [
            f"Severity: {event.severity}",
            f"Tenant: {event.tenant_id}",
            f"Trace: {event.trace_id}",
            f"Avg Score: {event.eval_avg_score:.2f}",
            f"Layer: {event.eval_layer}",
            f"Time: {event.created_at.isoformat()}",
            "",
            "--- Diagnostic Hints ---",
        ]
        for h in event.hints:
            lines.append(
                f"[{h.severity}] {h.dimension}: {h.message}\n"
                f"  Suggestion: {h.suggestion}"
            )
        return "\n".join(lines)


class DispatchAbuseNotificationUseCase:
    """Issue #68 P7c：異常控管告警 / 摘要 → notify_abuse 渠道（依指紋節流）。"""

    def __init__(
        self,
        channel_repo: NotificationChannelRepository,
        throttle_service: NotificationThrottleService,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._channel_repo = channel_repo
        self._throttle = throttle_service
        self._dispatcher = dispatcher

    async def execute(self, event: AbuseAlertEvent) -> int:
        sent = 0
        try:
            channels = await self._channel_repo.list_enabled()
            for ch in channels:
                if not ch.notify_abuse:
                    continue
                if await self._throttle.is_throttled(event.fingerprint, ch.id):
                    continue
                await self._dispatcher.send_to_channel(
                    ch, event.title, self.format_body(event)
                )
                await self._throttle.record_sent(
                    event.fingerprint, ch.id, ch.throttle_minutes * 60
                )
                sent += 1
        except Exception:
            _logger.warning("notification.abuse_dispatch_failed", exc_info=True)
        return sent

    @staticmethod
    def format_body(event: AbuseAlertEvent) -> str:
        """不含使用者原文與完整 id。"""
        lines = [f"租戶：{event.tenant_id}", f"事件：{event.kind.value}"]
        if event.kind is AbuseAlertKind.ESCALATION:
            lines += [
                f"主體：{event.subject_kind} {event.subject_masked}",
                f"通路：{event.channel or '-'}",
                f"等級：L{event.level}",
                f"原因：{'、'.join(event.reasons) or '-'}",
                f"剩餘：{event.retry_after} 秒",
            ]
        lines += list(event.summary_lines)
        lines.append(f"時間：{event.created_at.isoformat(timespec='seconds')}")
        return "\n".join(lines)
