"""BDD Step Definitions — Error Event Tracking."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.observability.error_event_use_cases import (
    ListErrorEventsUseCase,
    ReportErrorCommand,
    ReportErrorUseCase,
    ResolveErrorEventUseCase,
)
from src.application.observability.notification_use_cases import (
    DispatchNotificationUseCase,
    NotificationDispatcher,
)
from src.domain.observability.error_event import (
    ErrorEvent,
    ErrorEventRepository,
    compute_fingerprint,
    normalize_path,
)
from src.domain.observability.notification import (
    NotificationChannel,
    NotificationChannelRepository,
    NotificationSender,
    NotificationThrottleService,
)

scenarios("unit/observability/error_event_tracking.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def context():
    return {}


# -----------------------------------------------------------------------
# Scenario: 後端錯誤被捕捉並建立 error_event
# -----------------------------------------------------------------------


@given('一個 500 錯誤發生在路徑 "/api/v1/agent/chat" 方法 "POST"')
def backend_error_occurs(context):
    repo = AsyncMock(spec=ErrorEventRepository)
    repo.save.side_effect = lambda e: e
    context["repo"] = repo
    context["command"] = ReportErrorCommand(
        source="backend",
        error_type="ValueError",
        message="invalid input",
        path="/api/v1/agent/chat",
        method="POST",
        status_code=500,
    )


@when("系統呼叫 ReportErrorUseCase 回報錯誤", target_fixture="result")
def report_backend_error(context):
    uc = ReportErrorUseCase(error_event_repo=context["repo"])
    return _run(uc.execute(context["command"]))


@then("應建立一個 error_event 記錄")
def verify_event_created(result):
    assert result is not None
    assert result.id is not None
    assert result.source == "backend"


@then("fingerprint 應為非空字串")
def verify_fingerprint_not_empty(result):
    assert result.fingerprint
    assert len(result.fingerprint) > 0


# -----------------------------------------------------------------------
# Scenario: 前端錯誤透過公開 API 回報成功
# -----------------------------------------------------------------------


@given("前端發送一個 TypeError 錯誤報告")
def frontend_error_report(context):
    repo = AsyncMock(spec=ErrorEventRepository)
    repo.save.side_effect = lambda e: e
    context["repo"] = repo
    context["command"] = ReportErrorCommand(
        source="frontend",
        error_type="TypeError",
        message="Cannot read property 'x' of undefined",
        path="/chat",
    )


@when("系統呼叫 ReportErrorUseCase 回報前端錯誤", target_fixture="result")
def report_frontend_error(context):
    uc = ReportErrorUseCase(error_event_repo=context["repo"])
    return _run(uc.execute(context["command"]))


@then('應建立一個 source 為 "frontend" 的 error_event')
def verify_frontend_source(result):
    assert result.source == "frontend"


# -----------------------------------------------------------------------
# Scenario: Fingerprint 正規化路徑中的 UUID 和數字 ID
# -----------------------------------------------------------------------


@given(
    '路徑 "/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000/messages"'
)
def path_with_uuid(context):
    context["path"] = (
        "/api/v1/conversations/550e8400-e29b-41d4-a716-446655440000/messages"
    )


@when("計算 fingerprint", target_fixture="normalized")
def compute_fp(context):
    return normalize_path(context["path"])


@then('正規化路徑應為 "/api/v1/conversations/:id/messages"')
def verify_normalized_path(normalized):
    assert normalized == "/api/v1/conversations/:id/messages"


# -----------------------------------------------------------------------
# Scenario: 依 resolved 狀態過濾列表
# -----------------------------------------------------------------------


@given("系統中有 3 個 error_event 其中 1 個已標記 resolved")
def setup_events_with_resolved(context):
    repo = AsyncMock(spec=ErrorEventRepository)
    unresolved = [
        ErrorEvent(
            id=f"evt-{i}",
            fingerprint="fp1",
            source="backend",
            error_type="ValueError",
            message=f"error {i}",
            resolved=False,
        )
        for i in range(2)
    ]
    repo.list_events.return_value = (unresolved, 2)
    context["repo"] = repo


@when("查詢 resolved=false 的 error_event 列表", target_fixture="list_result")
def list_unresolved(context):
    uc = ListErrorEventsUseCase(error_event_repo=context["repo"])
    return _run(uc.execute(resolved=False))


@then("應回傳 2 個 error_event")
def verify_list_count(list_result):
    items, total = list_result
    assert len(items) == 2
    assert total == 2


# -----------------------------------------------------------------------
# Scenario: 標記 error event 為已處理
# -----------------------------------------------------------------------


@given("系統中有一個未處理的 error_event")
def setup_unresolved_event(context):
    now = datetime.now(timezone.utc)
    resolved_event = ErrorEvent(
        id="evt-1",
        fingerprint="fp1",
        source="backend",
        error_type="ValueError",
        message="error",
        resolved=True,
        resolved_at=now,
        resolved_by="admin@test.com",
    )
    repo = AsyncMock(spec=ErrorEventRepository)
    repo.resolve.return_value = resolved_event
    context["repo"] = repo


@when("標記該 error_event 為已處理", target_fixture="resolve_result")
def resolve_event(context):
    uc = ResolveErrorEventUseCase(error_event_repo=context["repo"])
    return _run(uc.execute("evt-1", "admin@test.com"))


@then("error_event 的 resolved 應為 true")
def verify_resolved(resolve_result):
    assert resolve_result.resolved is True


@then("resolved_at 應為非空")
def verify_resolved_at(resolve_result):
    assert resolve_result.resolved_at is not None


@then('resolved_by 應為 "admin@test.com"')
def verify_resolved_by(resolve_result):
    assert resolve_result.resolved_by == "admin@test.com"


# -----------------------------------------------------------------------
# Scenario: 重複 fingerprint 不重複寄信（throttle）
# -----------------------------------------------------------------------


@given("通知渠道已啟用且 throttle 為 15 分鐘")
def setup_enabled_channel(context):
    channel = NotificationChannel(
        id="ch-1",
        channel_type="email",
        name="Ops Email",
        enabled=True,
        throttle_minutes=15,
    )
    channel_repo = AsyncMock(spec=NotificationChannelRepository)
    channel_repo.list_enabled.return_value = [channel]

    throttle = AsyncMock(spec=NotificationThrottleService)
    throttle.is_throttled.return_value = False
    throttle.record_sent.return_value = None

    sender = AsyncMock(spec=NotificationSender)
    sender.channel_type.return_value = "email"
    dispatcher = NotificationDispatcher(senders={"email": sender})

    context["channel_repo"] = channel_repo
    context["throttle"] = throttle
    context["dispatcher"] = dispatcher
    context["sender"] = sender
    context["fingerprint"] = compute_fingerprint(
        "backend", "ValueError", "/api/v1/agent/chat"
    )


@given("throttle 服務回報該 fingerprint 已被節流")
def setup_throttled(context):
    context["throttle"].is_throttled.return_value = True


@when("同一 fingerprint 的新錯誤發生", target_fixture="dispatch_result")
def dispatch_throttled(context):
    event = ErrorEvent(
        id="evt-new",
        fingerprint=context["fingerprint"],
        source="backend",
        error_type="ValueError",
        message="error",
        path="/api/v1/agent/chat",
    )
    uc = DispatchNotificationUseCase(
        channel_repo=context["channel_repo"],
        throttle_service=context["throttle"],
        dispatcher=context["dispatcher"],
    )
    _run(uc.execute(event))
    return True


@then("不應觸發新的通知")
def verify_no_notification(context):
    context["sender"].send.assert_not_called()
