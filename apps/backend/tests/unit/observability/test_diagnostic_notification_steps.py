"""BDD step definitions for diagnostic notification dispatch."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.observability.notification_use_cases import (
    DispatchDiagnosticNotificationUseCase,
    DispatchNotificationUseCase,
    NotificationDispatcher,
)
from src.domain.observability.diagnostic import DiagnosticEvent, DiagnosticHint
from src.domain.observability.error_event import ErrorEvent
from src.domain.observability.notification import NotificationChannel

scenarios("unit/observability/diagnostic_notification.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def _make_channel(
    notify_diagnostics=False,
    diagnostic_severity="critical",
    min_severity="all",
):
    return NotificationChannel(
        id="ch-1",
        channel_type="email",
        name="Test Channel",
        enabled=True,
        throttle_minutes=15,
        min_severity=min_severity,
        notify_diagnostics=notify_diagnostics,
        diagnostic_severity=diagnostic_severity,
    )


def _make_diagnostic_event(severity="critical"):
    return DiagnosticEvent(
        fingerprint=f"diag|context_precision|{severity}",
        severity=severity,
        tenant_id="tenant-1",
        trace_id="trace-1",
        hints=[
            DiagnosticHint(
                category="data_source",
                severity=severity,
                dimension="context_precision",
                message="檢索結果與問題幾乎無關",
                suggestion="檢查知識庫",
            )
        ],
        eval_avg_score=0.25,
        eval_layer="L1+L2",
        created_at=datetime.now(timezone.utc),
    )


def _make_error_event():
    return ErrorEvent(
        id="err-1",
        fingerprint="abc123",
        source="backend",
        error_type="ValueError",
        message="test error",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture()
def context():
    return {}


# --- Given ---


@given("有一個已啟用且訂閱診斷告警的通知管道")
def given_channel_with_diagnostics(context):
    context["channel"] = _make_channel(notify_diagnostics=True)


@given("有一個已啟用但未訂閱診斷告警的通知管道")
def given_channel_without_diagnostics(context):
    context["channel"] = _make_channel(notify_diagnostics=False)


@given("有一個已啟用且診斷嚴重度設為 critical 的管道")
def given_channel_critical_only(context):
    context["channel"] = _make_channel(
        notify_diagnostics=True, diagnostic_severity="critical"
    )


@given("有一個已啟用且診斷嚴重度設為 warning 的管道")
def given_channel_warning_severity(context):
    context["channel"] = _make_channel(
        notify_diagnostics=True, diagnostic_severity="warning"
    )


@given("有一個已啟用但 min_severity 設為 off 的通知管道")
def given_channel_min_severity_off(context):
    context["channel"] = _make_channel(min_severity="off")


@given("有一個 critical 級別的診斷事件")
def given_critical_diagnostic_event(context):
    context["diagnostic_event"] = _make_diagnostic_event("critical")


@given("有一個 warning 級別的診斷事件")
def given_warning_diagnostic_event(context):
    context["diagnostic_event"] = _make_diagnostic_event("warning")


@given("有一個錯誤事件")
def given_error_event(context):
    context["error_event"] = _make_error_event()


# --- When ---


@when("執行診斷通知派發")
def when_dispatch_diagnostic(context):
    channel_repo = AsyncMock()
    channel_repo.list_enabled.return_value = [context["channel"]]

    throttle = AsyncMock()
    throttle.is_throttled.return_value = False

    dispatcher = MagicMock(spec=NotificationDispatcher)
    dispatcher.send_to_channel = AsyncMock()

    uc = DispatchDiagnosticNotificationUseCase(
        channel_repo=channel_repo,
        throttle_service=throttle,
        dispatcher=dispatcher,
    )
    _run(uc.execute(context["diagnostic_event"]))
    context["dispatcher"] = dispatcher


@when("執行錯誤通知派發")
def when_dispatch_error(context):
    channel_repo = AsyncMock()
    channel_repo.list_enabled.return_value = [context["channel"]]

    throttle = AsyncMock()
    throttle.is_throttled.return_value = False

    dispatcher = MagicMock(spec=NotificationDispatcher)
    dispatcher.send_to_channel = AsyncMock()

    uc = DispatchNotificationUseCase(
        channel_repo=channel_repo,
        throttle_service=throttle,
        dispatcher=dispatcher,
    )
    _run(uc.execute(context["error_event"]))
    context["dispatcher"] = dispatcher


# --- Then ---


@then("通知應成功發送到該管道")
def then_notification_sent(context):
    context["dispatcher"].send_to_channel.assert_called_once()


@then("通知不應發送")
def then_notification_not_sent(context):
    context["dispatcher"].send_to_channel.assert_not_called()
